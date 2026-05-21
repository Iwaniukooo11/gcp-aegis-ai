"""In-memory deduplication for Slack Events API retries."""

import time

_TTL_SECONDS = 600
_seen: dict[str, float] = {}


def is_duplicate_event(event_id: str | None) -> bool:
    """Return True if this event_id was already handled within the TTL window."""
    if not event_id:
        return False
    now = time.time()
    cutoff = now - _TTL_SECONDS
    stale = [key for key, seen_at in _seen.items() if seen_at < cutoff]
    for key in stale:
        del _seen[key]
    if event_id in _seen:
        return True
    _seen[event_id] = now
    return False
