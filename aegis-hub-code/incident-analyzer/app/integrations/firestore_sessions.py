"""Firestore integration for Incident Analyzer.

Incident Analyzer is the write-once owner of:
  - sessions/{incident_id}       (conversation seed for Query Processor)
  - incident_receipts/{key}      (deduplication receipts)
"""
import hashlib
from datetime import datetime, timedelta, timezone

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from app.config import get_settings

_client: firestore.Client | None = None


def _get_client() -> firestore.Client:
    global _client
    if _client is None:
        s = get_settings()
        _client = firestore.Client(
            project=s.gcp_project,
            database=s.firestore_database,
        )
    return _client


def build_idempotency_key(client_project_id: str, insert_id: str, timestamp: str, pod_name: str) -> str:
    """Build a stable deduplication key from log metadata."""
    raw = f"{client_project_id}:{insert_id}:{timestamp}:{pod_name}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_receipt(idempotency_key: str) -> dict | None:
    """Return the deduplication receipt document or None if not found."""
    db = _get_client()
    doc = db.collection("incident_receipts").document(idempotency_key).get()
    return doc.to_dict() if doc.exists else None


def create_receipt(idempotency_key: str, incident_id: str, metadata: dict) -> bool:
    """Create a deduplication receipt and return True when this request claimed it."""
    db = _get_client()
    s = get_settings()
    now = datetime.now(tz=timezone.utc)
    ttl = now + timedelta(hours=s.receipt_ttl_hours)
    try:
        db.collection("incident_receipts").document(idempotency_key).create(
            {
                "idempotency_key": idempotency_key,
                "incident_id": incident_id,
                "analysis_completed": False,
                "bigquery_persisted": False,
                "session_created": False,
                "slack_handoff_succeeded": False,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "ttl": ttl,
                **metadata,
            }
        )
        return True
    except AlreadyExists:
        return False


def update_receipt(idempotency_key: str, updates: dict) -> None:
    """Update fields on an existing deduplication receipt."""
    db = _get_client()
    db.collection("incident_receipts").document(idempotency_key).update(
        {**updates, "updated_at": datetime.now(tz=timezone.utc).isoformat()}
    )


def create_session(
    incident_id: str,
    client_project_id: str,
    service_name: str,
    cluster_name: str,
    namespace: str,
    severity: str,
    error_type: str,
    ai_summary: str,
    initial_model_content: str,
    log_timestamp: str = "",
) -> None:
    """Create the initial Firestore session document for follow-up queries.

    Query Processor depends on this document existing before it handles
    any follow-up app mentions for this incident.
    """
    db = _get_client()
    s = get_settings()
    now = datetime.now(tz=timezone.utc)
    ttl = now + timedelta(hours=s.session_ttl_hours)
    db.collection("sessions").document(incident_id).set(
        {
            "incident_id": incident_id,
            "client_project_id": client_project_id,
            "service_name": service_name,
            "cluster_name": cluster_name,
            "namespace": namespace,
            "severity": severity,
            "error_type": error_type,
            "ai_summary": ai_summary,
            "messages": [
                {"role": "model", "content": initial_model_content}
            ],
            "created_at": now.isoformat(),
            "log_timestamp": log_timestamp or now.isoformat(),
            "updated_at": now.isoformat(),
            "ttl": ttl,
        }
    )
