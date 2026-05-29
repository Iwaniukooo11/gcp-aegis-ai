"""Pub/Sub push endpoint for Incident Analyzer."""
import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.config import get_settings
from app.integrations import (
    bigquery_incidents,
    firestore_sessions,
    slack_gateway_client,
    vertex,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class PubSubMessage(BaseModel):
    data: str
    messageId: str
    publishTime: str
    attributes: dict = {}


class PubSubEnvelope(BaseModel):
    message: PubSubMessage
    subscription: str


def _generate_incident_id() -> str:
    now = datetime.now(tz=timezone.utc)
    seq = str(now.microsecond + now.second * 1_000_000)[-6:].zfill(6)
    return f"INC-{now.year}-{seq}"


def _str_field(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _extract_log_fields(log_entry: dict) -> dict:
    resource = log_entry.get("resource", {})
    labels = resource.get("labels", {})
    log_name = _str_field(log_entry.get("logName"))
    project_from_log_name = ""
    if "/projects/" in log_name:
        project_from_log_name = log_name.split("/")[1]
    return {
        "insert_id": _str_field(log_entry.get("insertId")),
        "client_project_id": _str_field(
            labels.get("project_id"),
            project_from_log_name or "unknown",
        ),
        "resource_type": _str_field(resource.get("type")),
        "cluster_name": _str_field(labels.get("cluster_name")),
        "namespace": _str_field(labels.get("namespace_name"), "default"),
        "service_name": _str_field(
            labels.get("container_name") or labels.get("service_name"),
            "unknown",
        ),
        "pod_name": _str_field(labels.get("pod_name")),
        "severity": _str_field(log_entry.get("severity"), "ERROR"),
        "timestamp": log_entry.get("timestamp", ""),
        "text_payload": log_entry.get("textPayload", ""),
        "json_payload": log_entry.get("jsonPayload", {}),
        "labels": log_entry.get("labels", {}),
    }


def _hub_received_at() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _fallback_normalized(fields: dict, log_entry: dict) -> dict:
    json_payload = log_entry.get("jsonPayload") or fields.get("json_payload") or {}
    if not isinstance(json_payload, dict):
        json_payload = {}
    error_type = str(json_payload.get("error_type") or "")
    short_message = str(
        json_payload.get("message") or fields.get("text_payload") or error_type or "Unknown error"
    )[:120]
    if short_message.strip() == "Request completed" and error_type:
        short_message = error_type[:120]
    return {
        "error_type": error_type,
        "short_message": short_message,
        "stack_trace_preview": str(json_payload.get("stack_trace_preview") or "")[:500],
        "service_name": str(json_payload.get("service_name") or fields.get("service_name", "")),
        "severity": str(json_payload.get("severity") or fields.get("severity", "ERROR")),
    }


def _run_gemini_enrichment(
    incident_id: str,
    log_entry: dict,
    fields: dict,
) -> dict:
    normalized: dict = {}
    classification: dict = {}
    formatted_message = ""
    ai_summary = ""
    ai_recommendation = ""
    terminal_status = "FAILED"
    terminal_failure_reason = ""

    try:
        normalized = vertex.normalize_log(log_entry)
        classification = vertex.classify_incident(normalized, log_entry)
        ai_summary = classification.get("ai_summary", "")
        ai_recommendation = classification.get("ai_recommendation", "")
        formatted_message = vertex.format_slack_alert(incident_id, normalized, classification)
        terminal_status = "SUCCESS"
    except Exception as exc:
        logger.warning("Gemini enrichment failed for %s: %s", incident_id, exc)
        terminal_status = "PARTIAL_SUCCESS"
        terminal_failure_reason = f"gemini_error: {type(exc).__name__}"
        normalized = normalized or _fallback_normalized(fields, log_entry)

    fallback_text = (
        f"Incident {incident_id} in {fields['client_project_id']}/"
        f"{normalized.get('service_name', fields['service_name'])} "
        f"with severity {fields['severity']} was detected, but AI analysis is currently unavailable."
    )

    return {
        "normalized": normalized,
        "classification": classification,
        "formatted_message": formatted_message,
        "ai_summary": ai_summary,
        "ai_recommendation": ai_recommendation,
        "terminal_status": terminal_status,
        "terminal_failure_reason": terminal_failure_reason,
        "fallback_text": fallback_text,
    }


def _build_row(
    incident_id: str,
    idem_key: str,
    fields: dict,
    pipeline: dict,
    hub_received: str,
) -> dict:
    normalized = pipeline["normalized"]
    return bigquery_incidents.build_incident_row(
        incident_id=incident_id,
        idempotency_key=idem_key,
        event_id=f"{fields['client_project_id']}-{fields['insert_id']}-{fields['timestamp']}",
        source_log_insert_id=fields["insert_id"],
        client_project_id=fields["client_project_id"],
        resource_type=fields["resource_type"],
        cluster_name=fields["cluster_name"],
        namespace=fields["namespace"],
        service_name=normalized.get("service_name") or fields["service_name"],
        pod_name=fields["pod_name"],
        severity=fields["severity"],
        error_type=normalized.get("error_type", ""),
        short_message=normalized.get("short_message", ""),
        stack_trace_preview=normalized.get("stack_trace_preview", ""),
        labels_json=json.dumps(fields["labels"]),
        ai_summary=pipeline.get("ai_summary", ""),
        ai_recommendation=pipeline.get("ai_recommendation", ""),
        terminal_status=pipeline.get("terminal_status", "FAILED"),
        terminal_failure_reason=pipeline.get("terminal_failure_reason", ""),
        hub_received_at=hub_received,
        log_timestamp=fields.get("timestamp", ""),
    )


def _ensure_pipeline(
    incident_id: str,
    log_entry: dict,
    fields: dict,
    receipt: dict,
    idem_key: str,
) -> dict:
    pipeline = receipt.get("pipeline") or {}
    if pipeline.get("normalized"):
        return pipeline

    pipeline = _run_gemini_enrichment(incident_id, log_entry, fields)
    firestore_sessions.update_receipt(idem_key, {"pipeline": pipeline})
    return pipeline


def _persist_bigquery(
    incident_id: str,
    idem_key: str,
    fields: dict,
    pipeline: dict,
    receipt: dict,
) -> None:
    if receipt.get("bigquery_persisted"):
        return

    hub_received = receipt.get("hub_received_at") or _hub_received_at()
    row = _build_row(incident_id, idem_key, fields, pipeline, hub_received)
    bigquery_incidents.insert_incident(row)
    firestore_sessions.update_receipt(idem_key, {"bigquery_persisted": True})


def _persist_session(
    incident_id: str,
    idem_key: str,
    fields: dict,
    pipeline: dict,
    receipt: dict,
) -> None:
    if receipt.get("session_created") or firestore_sessions.get_session(incident_id):
        if not receipt.get("session_created"):
            firestore_sessions.update_receipt(idem_key, {"session_created": True})
        return

    normalized = pipeline["normalized"]
    service_name = normalized.get("service_name") or fields["service_name"]
    ai_summary = pipeline.get("ai_summary", "")
    initial_content = (
        f"Incident {incident_id}: {service_name} reported {normalized.get('error_type', 'an error')}. "
        f"Initial AI summary: {ai_summary}"
        if ai_summary
        else f"Incident {incident_id}: {service_name} — AI analysis unavailable."
    )

    firestore_sessions.create_session(
        incident_id=incident_id,
        client_project_id=fields["client_project_id"],
        service_name=service_name,
        cluster_name=fields["cluster_name"],
        namespace=fields["namespace"],
        severity=fields["severity"],
        error_type=normalized.get("error_type", ""),
        ai_summary=ai_summary,
        initial_model_content=initial_content,
        log_timestamp=fields.get("timestamp", ""),
    )
    firestore_sessions.update_receipt(idem_key, {"session_created": True})


def _handoff_slack(
    incident_id: str,
    idem_key: str,
    fields: dict,
    pipeline: dict,
    receipt: dict,
) -> None:
    if receipt.get("slack_handoff_succeeded"):
        return

    normalized = pipeline["normalized"]
    service_name = normalized.get("service_name") or fields["service_name"]
    settings = get_settings()
    channel = settings.slack_alert_channel_id.strip()

    try:
        gateway_response = slack_gateway_client.post_alert(
            incident_id=incident_id,
            client_project_id=fields["client_project_id"],
            service_name=service_name,
            severity=fields["severity"],
            error_type=normalized.get("error_type", ""),
            short_message=normalized.get("short_message", ""),
            stack_trace_preview=normalized.get("stack_trace_preview", ""),
            ai_summary=pipeline.get("ai_summary", ""),
            ai_recommendation=pipeline.get("ai_recommendation", ""),
            formatted_message=pipeline.get("formatted_message", ""),
            fallback_text=pipeline.get("fallback_text", ""),
        )
    except Exception as exc:
        error_text = str(exc)[:500]
        firestore_sessions.update_receipt(
            idem_key,
            {"slack_handoff_error": error_text},
        )
        logger.error("Slack Gateway handoff failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="slack_gateway_failed") from exc

    message_ts = str(gateway_response.get("ts", ""))
    if channel and message_ts and receipt.get("bigquery_persisted"):
        try:
            bigquery_incidents.update_incident_slack_delivery(
                incident_id=incident_id,
                slack_channel=channel,
                slack_message_ts=message_ts,
            )
        except Exception as exc:
            logger.warning(
                "BigQuery Slack delivery update failed for %s: %s",
                incident_id,
                exc,
            )

    firestore_sessions.update_receipt(
        idem_key,
        {"slack_handoff_succeeded": True, "slack_handoff_error": ""},
    )


def _process_incident(
    incident_id: str,
    idem_key: str,
    log_entry: dict,
    fields: dict,
    receipt: dict,
) -> dict:
    pipeline = _ensure_pipeline(incident_id, log_entry, fields, receipt, idem_key)

    try:
        _persist_bigquery(incident_id, idem_key, fields, pipeline, receipt)
        receipt = firestore_sessions.get_receipt(idem_key) or receipt
    except Exception as exc:
        logger.error("BigQuery insert failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="bigquery_insert_failed") from exc

    try:
        _persist_session(incident_id, idem_key, fields, pipeline, receipt)
    except Exception as exc:
        logger.error("Firestore session creation failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="firestore_session_failed") from exc

    receipt = firestore_sessions.get_receipt(idem_key) or receipt
    _handoff_slack(incident_id, idem_key, fields, pipeline, receipt)

    terminal_status = pipeline.get("terminal_status", "FAILED")
    logger.info("Incident %s processed with status %s", incident_id, terminal_status)
    return {"status": terminal_status, "incident_id": incident_id}


@router.post("/pubsub/push", status_code=status.HTTP_200_OK)
async def receive_pubsub(envelope: PubSubEnvelope, request: Request) -> dict:
    """Receive an authenticated Pub/Sub push message and process it as an incident."""
    try:
        raw_bytes = base64.b64decode(envelope.message.data)
        log_entry = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to decode Pub/Sub message: %s", exc)
        return {"status": "ack_bad_payload"}

    hub_received = _hub_received_at()
    fields = _extract_log_fields(log_entry)
    idem_key = firestore_sessions.build_idempotency_key(
        fields["client_project_id"],
        fields["insert_id"],
        fields["timestamp"],
        fields["pod_name"],
    )

    existing = firestore_sessions.get_receipt(idem_key)
    if existing and existing.get("slack_handoff_succeeded"):
        logger.info("Duplicate delivery for %s — already complete", idem_key)
        return {"status": "duplicate", "incident_id": existing.get("incident_id")}

    metadata = {
        "client_project_id": fields["client_project_id"],
        "source_log_insert_id": fields["insert_id"],
        "source_timestamp": fields["timestamp"],
        "pod_name": fields["pod_name"],
        "hub_received_at": hub_received,
    }

    if existing:
        receipt = existing
        incident_id = receipt.get("incident_id")
        if not incident_id:
            logger.error("Receipt %s missing incident_id — cannot resume", idem_key)
            raise HTTPException(status_code=500, detail="receipt_missing_incident_id")
        logger.info("Resuming incident %s for idempotency key %s", incident_id, idem_key)
    else:
        incident_id = _generate_incident_id()
        receipt, _ = firestore_sessions.claim_receipt(idem_key, incident_id, metadata)
        incident_id = receipt.get("incident_id") or incident_id

    return _process_incident(incident_id, idem_key, log_entry, fields, receipt)
