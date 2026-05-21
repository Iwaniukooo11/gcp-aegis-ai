"""Firestore session read/update for Query Processor.

Query Processor reads and appends to sessions created by Incident Analyzer.
It never creates sessions — that is Incident Analyzer's responsibility.
"""
from datetime import datetime, timedelta, timezone

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


def get_session(incident_id: str) -> dict | None:
    """Return the session document for incident_id, or None if not found."""
    db = _get_client()
    doc = db.collection("sessions").document(incident_id).get()
    return doc.to_dict() if doc.exists else None


def append_messages(incident_id: str, new_messages: list[dict]) -> None:
    """Append new messages to the session and extend the TTL.

    new_messages should be dicts like {"role": "user"|"model", "content": "..."}.
    """
    db = _get_client()
    s = get_settings()
    now = datetime.now(tz=timezone.utc)
    ttl = now + timedelta(hours=s.session_ttl_hours)

    doc_ref = db.collection("sessions").document(incident_id)
    doc_ref.update(
        {
            "messages": firestore.ArrayUnion(new_messages),
            "updated_at": now.isoformat(),
            "ttl": ttl,
        }
    )
