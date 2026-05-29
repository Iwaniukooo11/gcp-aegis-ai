"""Slack Events API deduplication (Firestore with in-memory fallback)."""

import logging
import time

from app.integrations import firestore_dedup

logger = logging.getLogger(__name__)

_TTL_SECONDS = 600
_seen: dict[str, float] = {}


def _is_duplicate_in_memory(event_id: str) -> bool:
    now = time.time()
    cutoff = now - _TTL_SECONDS
    stale = [key for key, seen_at in _seen.items() if seen_at < cutoff]
    for key in stale:
        del _seen[key]
    if event_id in _seen:
        return True
    _seen[event_id] = now
    return False


def is_duplicate_event(event_id: str | None) -> bool:
    if not event_id:
        return False

    try:
        if firestore_dedup.claim_event(event_id):
            return False
        return True
    except Exception as exc:
        logger.warning("Firestore dedup failed for %s: %s — using memory", event_id, exc)
        return _is_duplicate_in_memory(event_id)
