"""Cross-instance Slack Events deduplication via Firestore."""

from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from app.config import get_settings

_client: firestore.Client | None = None
_COLLECTION = "slack_processed_events"
_TTL_MINUTES = 10


def _get_client() -> firestore.Client | None:
    global _client
    s = get_settings()
    if not s.gcp_project.strip():
        return None
    if _client is None:
        _client = firestore.Client(
            project=s.gcp_project,
            database=s.firestore_database,
        )
    return _client


def claim_event(event_id: str) -> bool:
    """Return True if this event_id is new and was claimed for processing."""
    client = _get_client()
    if client is None:
        return True

    doc_ref = client.collection(_COLLECTION).document(event_id)
    now = datetime.now(tz=timezone.utc)
    ttl = now + timedelta(minutes=_TTL_MINUTES)

    doc = doc_ref.get()
    if doc.exists:
        return False

    doc_ref.set({"event_id": event_id, "claimed_at": now.isoformat(), "ttl": ttl})
    return True
