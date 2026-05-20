"""Pub/Sub push endpoint for Incident Analyzer.

Processing order (spec §5.2):
  1. Verify OIDC
  2. Decode + extract log fields
  3. Dedup check (Firestore receipts)
  4. Generate incident_id
  5. Gemini 1-3
  6. BigQuery insert
  7. Firestore session create
  8. Receipt update
  9. Slack Gateway handoff
"""
import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

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
    """Generate a human-readable incident ID: INC-YYYY-NNNNNN.

    Uses current UTC timestamp millis as the sequence suffix for simplicity
    in MVP. This is not guaranteed globally unique under high concurrency —
    acceptable for student-scale deployment.
    """
    now = datetime.now(tz=timezone.utc)
    seq = str(now.microsecond + now.second * 1_000_000)[-6:].zfill(6)
    return f"INC-{now.year}-{seq}"


def _extract_log_fields(log_entry: dict) -> dict:
    """Pull the fields Incident Analyzer needs from a Cloud Logging LogEntry."""
    resource = log_entry.get("resource", {})
    labels = resource.get("labels", {})
    return {
        "insert_id": log_entry.get("insertId", ""),
        "client_project_id": labels.get("project_id", log_entry.get("logName", "").split("/")[1] if "/projects/" in log_entry.get("logName", "") else ""),
        "resource_type": resource.get("type", ""),
        "cluster_name": labels.get("cluster_name", ""),
        "namespace": labels.get("namespace_name", "default"),
        "service_name": labels.get("container_name", labels.get("service_name", "")),
        "pod_name": labels.get("pod_name", ""),
        "severity": log_entry.get("severity", "ERROR"),
        "timestamp": log_entry.get("timestamp", ""),
        "text_payload": log_entry.get("textPayload", ""),
        "json_payload": log_entry.get("jsonPayload", {}),
        "labels": log_entry.get("labels", {}),
    }


@router.post("/pubsub/push", status_code=status.HTTP_200_OK)
async def receive_pubsub(envelope: PubSubEnvelope, request: Request) -> dict:
    """Receive an authenticated Pub/Sub push message and process it as an incident."""
    try:
        raw_bytes = base64.b64decode(envelope.message.data)
        log_entry = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to decode Pub/Sub message: %s", exc)
        # Return 200 to ack undecodeable messages — they should go to DLQ via
        # max_delivery_attempts, not loop forever.
        return {"status": "ack_bad_payload"}

    fields = _extract_log_fields(log_entry)
    idem_key = firestore_sessions.build_idempotency_key(
        fields["client_project_id"],
        fields["insert_id"],
        fields["timestamp"],
        fields["pod_name"],
    )

    existing = firestore_sessions.get_receipt(idem_key)
    if existing:
        logger.info("Duplicate delivery for %s — skipping", idem_key)
        return {"status": "duplicate"}

    incident_id = _generate_incident_id()
    firestore_sessions.create_receipt(
        idem_key,
        incident_id,
        {
            "client_project_id": fields["client_project_id"],
            "source_log_insert_id": fields["insert_id"],
            "source_timestamp": fields["timestamp"],
            "pod_name": fields["pod_name"],
        },
    )

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
        normalized = normalized or {
            "error_type": "",
            "short_message": fields.get("text_payload", "")[:120],
            "stack_trace_preview": "",
            "service_name": fields.get("service_name", ""),
            "severity": fields.get("severity", "ERROR"),
        }

    fallback_text = (
        f"Incident {incident_id} in {fields['client_project_id']}/{normalized.get('service_name', fields['service_name'])} "
        f"with severity {fields['severity']} was detected, but AI analysis is currently unavailable."
    )

    import json as _json
    row = bigquery_incidents.build_incident_row(
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
        labels_json=_json.dumps(fields["labels"]),
        ai_summary=ai_summary,
        ai_recommendation=ai_recommendation,
        terminal_status=terminal_status,
        terminal_failure_reason=terminal_failure_reason,
    )

    try:
        bigquery_incidents.insert_incident(row)
        firestore_sessions.update_receipt(idem_key, {"bigquery_persisted": True})
    except Exception as exc:
        logger.error("BigQuery insert failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="bigquery_insert_failed") from exc

    service_name = normalized.get("service_name") or fields["service_name"]
    initial_content = (
        f"Incident {incident_id}: {service_name} reported {normalized.get('error_type', 'an error')}. "
        f"Initial AI summary: {ai_summary}" if ai_summary
        else f"Incident {incident_id}: {service_name} — AI analysis unavailable."
    )

    try:
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
        )
        firestore_sessions.update_receipt(idem_key, {"session_created": True})
    except Exception as exc:
        logger.error("Firestore session creation failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="firestore_session_failed") from exc

    try:
        slack_gateway_client.post_alert(
            incident_id=incident_id,
            client_project_id=fields["client_project_id"],
            service_name=service_name,
            severity=fields["severity"],
            error_type=normalized.get("error_type", ""),
            short_message=normalized.get("short_message", ""),
            stack_trace_preview=normalized.get("stack_trace_preview", ""),
            ai_summary=ai_summary,
            ai_recommendation=ai_recommendation,
            formatted_message=formatted_message,
            fallback_text=fallback_text,
        )
        firestore_sessions.update_receipt(idem_key, {"slack_handoff_succeeded": True})
    except Exception as exc:
        logger.error("Slack Gateway handoff failed for %s: %s", incident_id, exc)
        # Return 500 so Pub/Sub retries — dedup receipt prevents a second BQ/Firestore write.
        raise HTTPException(status_code=500, detail="slack_gateway_failed") from exc

    logger.info("Incident %s processed with status %s", incident_id, terminal_status)
    return {"status": terminal_status, "incident_id": incident_id}
