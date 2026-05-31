"""Pub/Sub push endpoint for Incident Analyzer.

Processing order:
  1. Verify OIDC
  2. Decode + extract log fields
  3. Claim or load Firestore receipt
  4. Reuse incident_id on retry
  5. Gemini 1-3, or reuse completed analysis from receipt
  6. Firestore session create
  7. Slack Gateway handoff
  8. BigQuery insert with Slack evidence
  9. Receipt update after each completed milestone
"""
import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.integrations import (
    bigquery_incidents,
    firestore_sessions,
    slack_gateway_client,
    vertex,
)

logger = logging.getLogger(__name__)

router = APIRouter()
ERROR_SEVERITIES = {"ERROR", "CRITICAL", "ALERT", "EMERGENCY"}


class PubSubMessage(BaseModel):
    data: str
    messageId: str
    publishTime: str
    attributes: dict = Field(default_factory=dict)


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


def _extract_structured_payload(log_entry: dict) -> dict:
    payload = log_entry.get("jsonPayload")
    if isinstance(payload, dict):
        return payload

    text_payload = log_entry.get("textPayload", "")
    if not isinstance(text_payload, str):
        return {}

    try:
        decoded = json.loads(text_payload)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _is_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return False


def _extract_log_fields(log_entry: dict) -> dict:
    """Pull the fields Incident Analyzer needs from a Cloud Logging LogEntry."""
    resource = log_entry.get("resource", {})
    labels = resource.get("labels", {})
    payload = _extract_structured_payload(log_entry)
    log_name = log_entry.get("logName", "")
    project_from_log_name = log_name.split("/")[1] if "/projects/" in log_name else ""
    service_name = payload.get("service_name") or labels.get("container_name", labels.get("service_name", ""))
    severity = str(log_entry.get("severity") or payload.get("severity") or "DEFAULT").upper()
    if severity == "DEFAULT" and payload.get("severity"):
        severity = str(payload["severity"]).upper()
    return {
        "insert_id": log_entry.get("insertId", ""),
        "client_project_id": payload.get("client_project_id") or labels.get("project_id", project_from_log_name),
        "resource_type": resource.get("type", ""),
        "cluster_name": labels.get("cluster_name", ""),
        "namespace": labels.get("namespace_name", "default"),
        "service_name": service_name,
        "pod_name": labels.get("pod_name", ""),
        "severity": severity,
        "timestamp": log_entry.get("timestamp", ""),
        "text_payload": log_entry.get("textPayload", ""),
        "json_payload": payload,
        "labels": log_entry.get("labels", {}),
        "incident_candidate": _is_true(payload.get("incident_candidate")),
        "scenario": payload.get("scenario", ""),
        "error_type": payload.get("error_type", ""),
        "message": payload.get("message", ""),
        "stack_trace_preview": payload.get("stack_trace_preview", ""),
    }


def _should_process_incident(fields: dict) -> tuple[bool, str]:
    if fields["severity"] not in ERROR_SEVERITIES:
        return False, "severity_below_error"
    if not fields["incident_candidate"]:
        return False, "not_incident_candidate"
    return True, ""


def _is_completed_receipt(receipt: dict) -> bool:
    return bool(
        receipt.get("bigquery_persisted")
        and receipt.get("session_created")
        and receipt.get("slack_handoff_succeeded")
    )


def _fallback_normalized(fields: dict) -> dict:
    return {
        "error_type": fields.get("error_type", ""),
        "short_message": (fields.get("message") or fields.get("text_payload", ""))[:120],
        "stack_trace_preview": fields.get("stack_trace_preview", ""),
        "service_name": fields.get("service_name", ""),
        "severity": fields.get("severity", "ERROR"),
    }


def _analyze_or_load_from_receipt(
    log_entry: dict,
    fields: dict,
    incident_id: str,
    idem_key: str,
    receipt: dict,
) -> dict:
    if receipt.get("analysis_completed"):
        return {
            "normalized": receipt.get("normalized", _fallback_normalized(fields)),
            "classification": receipt.get("classification", {}),
            "formatted_message": receipt.get("formatted_message", ""),
            "terminal_status": receipt.get("terminal_status", "SUCCESS"),
            "terminal_failure_reason": receipt.get("terminal_failure_reason", ""),
        }

    normalized: dict = {}
    classification: dict = {}
    formatted_message = ""
    terminal_status = "FAILED"
    terminal_failure_reason = ""

    try:
        normalized = vertex.normalize_log(log_entry)
        classification = vertex.classify_incident(normalized, log_entry)
        formatted_message = vertex.format_slack_alert(incident_id, normalized, classification)
        terminal_status = "SUCCESS"
    except Exception as exc:
        logger.warning("Gemini enrichment failed for %s: %s", incident_id, exc)
        terminal_status = "PARTIAL_SUCCESS"
        terminal_failure_reason = f"gemini_error: {type(exc).__name__}"
        normalized = normalized or _fallback_normalized(fields)

    analysis = {
        "normalized": normalized,
        "classification": classification,
        "formatted_message": formatted_message,
        "terminal_status": terminal_status,
        "terminal_failure_reason": terminal_failure_reason,
    }
    firestore_sessions.update_receipt(idem_key, {"analysis_completed": True, **analysis})
    return analysis


def _build_initial_session_content(incident_id: str, service_name: str, error_type: str, ai_summary: str) -> str:
    if ai_summary:
        return (
            f"Incident {incident_id}: {service_name} reported {error_type or 'an error'}. "
            f"Initial AI summary: {ai_summary}"
        )
    return f"Incident {incident_id}: {service_name} - AI analysis unavailable."


def _build_fallback_text(incident_id: str, client_project_id: str, service_name: str, severity: str) -> str:
    return (
        f"Incident {incident_id} in {client_project_id}/{service_name} "
        f"with severity {severity} was detected, but AI analysis is currently unavailable."
    )


@router.post("/pubsub/push", status_code=status.HTTP_200_OK)
async def receive_pubsub(envelope: PubSubEnvelope, request: Request) -> dict:
    """Receive an authenticated Pub/Sub push message and process it as an incident."""
    hub_received_at = datetime.now(tz=timezone.utc).isoformat()
    try:
        raw_bytes = base64.b64decode(envelope.message.data)
        log_entry = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to decode Pub/Sub message: %s", exc)
        # Return 200 to ack undecodeable messages — they should go to DLQ via
        # max_delivery_attempts, not loop forever.
        return {"status": "ack_bad_payload"}

    fields = _extract_log_fields(log_entry)
    should_process, ignore_reason = _should_process_incident(fields)
    if not should_process:
        logger.info(
            "Ignoring log entry %s from %s: %s",
            fields.get("insert_id", ""),
            fields.get("client_project_id", ""),
            ignore_reason,
        )
        return {"status": "ignored", "reason": ignore_reason}

    idem_key = firestore_sessions.build_idempotency_key(
        fields["client_project_id"],
        fields["insert_id"],
        fields["timestamp"],
        fields["pod_name"],
    )

    receipt = firestore_sessions.get_receipt(idem_key)
    if receipt and _is_completed_receipt(receipt):
        logger.info("Completed duplicate delivery for %s - skipping", idem_key)
        return {"status": "duplicate", "incident_id": receipt.get("incident_id")}

    if receipt:
        incident_id = receipt["incident_id"]
        logger.info("Retry delivery for %s - resuming incident %s", idem_key, incident_id)
    else:
        incident_id = _generate_incident_id()
        created = firestore_sessions.create_receipt(
            idem_key,
            incident_id,
            {
                "client_project_id": fields["client_project_id"],
                "source_log_insert_id": fields["insert_id"],
                "source_timestamp": fields["timestamp"],
                "pod_name": fields["pod_name"],
                "hub_received_at": hub_received_at,
            },
        )
        if not created:
            receipt = firestore_sessions.get_receipt(idem_key)
            if receipt and _is_completed_receipt(receipt):
                return {"status": "duplicate", "incident_id": receipt.get("incident_id")}
            if not receipt:
                raise HTTPException(status_code=500, detail="receipt_claim_failed")
            incident_id = receipt["incident_id"]
        else:
            receipt = {
                "incident_id": incident_id,
                "analysis_completed": False,
                "bigquery_persisted": False,
                "session_created": False,
                "slack_handoff_succeeded": False,
            }

    analysis = _analyze_or_load_from_receipt(log_entry, fields, incident_id, idem_key, receipt)
    normalized = analysis["normalized"]
    classification = analysis["classification"]
    formatted_message = analysis["formatted_message"]
    terminal_status = analysis["terminal_status"]
    terminal_failure_reason = analysis["terminal_failure_reason"]
    ai_summary = classification.get("ai_summary", "")
    ai_recommendation = classification.get("ai_recommendation", "")
    service_name = normalized.get("service_name") or fields["service_name"]
    fallback_text = _build_fallback_text(
        incident_id,
        fields["client_project_id"],
        service_name,
        fields["severity"],
    )

    if not receipt.get("session_created"):
        initial_content = _build_initial_session_content(
            incident_id,
            service_name,
            normalized.get("error_type", ""),
            ai_summary,
        )
        try:
            firestore_sessions.create_session(
                incident_id=incident_id,
                client_project_id=fields["client_project_id"],
                service_name=service_name,
                cluster_name=fields["cluster_name"],
                namespace=fields["namespace"],
                pod_name=fields["pod_name"],
                severity=fields["severity"],
                error_type=normalized.get("error_type", ""),
                ai_summary=ai_summary,
                initial_model_content=initial_content,
                log_timestamp=fields.get("timestamp", ""),
            )
            firestore_sessions.update_receipt(idem_key, {"session_created": True})
            receipt["session_created"] = True
        except Exception as exc:
            logger.error("Firestore session creation failed for %s: %s", incident_id, exc)
            raise HTTPException(status_code=500, detail="firestore_session_failed") from exc

    slack_channel = receipt.get("slack_channel")
    slack_message_ts = receipt.get("slack_message_ts")
    first_alert_sent_at = receipt.get("first_alert_sent_at")

    if not receipt.get("slack_handoff_succeeded"):
        try:
            slack_response = slack_gateway_client.post_alert(
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
            slack_channel = slack_response.get("channel") or get_settings().slack_alert_channel_id or slack_channel
            slack_message_ts = slack_response.get("ts") or slack_message_ts
            first_alert_sent_at = datetime.now(tz=timezone.utc).isoformat()
            firestore_sessions.update_receipt(
                idem_key,
                {
                    "slack_handoff_succeeded": True,
                    "slack_channel": slack_channel,
                    "slack_message_ts": slack_message_ts,
                    "first_alert_sent_at": first_alert_sent_at,
                },
            )
            receipt["slack_handoff_succeeded"] = True
        except Exception as exc:
            logger.error("Slack Gateway handoff failed for %s: %s", incident_id, exc)
            raise HTTPException(status_code=500, detail="slack_gateway_failed") from exc

    if not receipt.get("bigquery_persisted"):
        try:
            if bigquery_incidents.incident_exists_by_idempotency_key(idem_key):
                firestore_sessions.update_receipt(idem_key, {"bigquery_persisted": True})
            else:
                row = bigquery_incidents.build_incident_row(
                    incident_id=incident_id,
                    idempotency_key=idem_key,
                    event_id=f"{fields['client_project_id']}-{fields['insert_id']}-{fields['timestamp']}",
                    source_log_insert_id=fields["insert_id"],
                    client_project_id=fields["client_project_id"],
                    resource_type=fields["resource_type"],
                    cluster_name=fields["cluster_name"],
                    namespace=fields["namespace"],
                    service_name=service_name,
                    pod_name=fields["pod_name"],
                    severity=fields["severity"],
                    error_type=normalized.get("error_type", ""),
                    short_message=normalized.get("short_message", ""),
                    stack_trace_preview=normalized.get("stack_trace_preview", ""),
                    labels_json=json.dumps(fields["labels"]),
                    ai_summary=ai_summary,
                    ai_recommendation=ai_recommendation,
                    terminal_status=terminal_status,
                    terminal_failure_reason=terminal_failure_reason,
                    slack_channel=slack_channel,
                    slack_message_ts=slack_message_ts,
                    first_alert_sent_at=first_alert_sent_at,
                    hub_received_at=receipt.get("hub_received_at") or hub_received_at,
                    log_timestamp=fields.get("timestamp", ""),
                )
                bigquery_incidents.insert_incident(row, insert_id=idem_key)
                firestore_sessions.update_receipt(idem_key, {"bigquery_persisted": True})
        except Exception as exc:
            logger.error("BigQuery insert failed for %s: %s", incident_id, exc)
            raise HTTPException(status_code=500, detail="bigquery_insert_failed") from exc

    logger.info("Incident %s processed with status %s", incident_id, terminal_status)
    return {"status": terminal_status, "incident_id": incident_id}
