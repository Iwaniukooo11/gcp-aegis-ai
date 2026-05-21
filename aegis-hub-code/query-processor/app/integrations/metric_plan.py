"""Metric plan helpers: question-driven supplements and result summaries."""

from datetime import datetime, timezone

from app.integrations.metric_catalog import GCP_METRIC_TYPE_BY_ID
from app.integrations.vertex import _build_k8s_container_filter, _normalize_metric_item

_QUESTION_METRIC_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("cpu", "cpu_utilization"),
    ("memory", "memory_utilization"),
    ("mem", "memory_utilization"),
    ("restart", "pod_restart_count"),
)


def supplement_metric_plan_for_question(plan: dict, question: str, session: dict) -> dict:
    """Ensure allowlisted metrics implied by the operator question are in the plan."""
    q = question.lower()
    try:
        window = int(plan.get("window_minutes", 30))
    except (TypeError, ValueError):
        window = 30
    window = max(5, min(window, 60))

    existing_types: set[str] = set()
    metrics = []
    for item in plan.get("metrics", []):
        if not isinstance(item, dict):
            continue
        type_id = str(item.get("type") or "").strip()
        if type_id in GCP_METRIC_TYPE_BY_ID:
            existing_types.add(type_id)
            spec = _normalize_metric_item({"type": type_id}, session, window)
            if spec is not None:
                metrics.append(spec)

    for keyword, type_id in _QUESTION_METRIC_KEYWORDS:
        if keyword in q and type_id not in existing_types:
            spec = _normalize_metric_item({"type": type_id}, session, window)
            if spec is not None:
                metrics.append(spec)
                existing_types.add(type_id)

    return {
        "metrics": metrics,
        "rationale": str(plan.get("rationale", "") or ""),
        "window_minutes": window,
    }


def parse_session_anchor(session: dict) -> datetime | None:
    """Return incident time from session created_at for Monitoring lookback."""
    raw = session.get("created_at")
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(raw, datetime):
        ts = raw
    else:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def summarize_metric_results(metric_results: dict) -> dict:
    """Build a compact summary for Slack formatting (latest point per metric)."""
    summary: dict = {}
    for metric_key, payload in metric_results.items():
        if isinstance(payload, dict) and payload.get("error"):
            summary[metric_key] = {"status": "error", "detail": payload["error"]}
            continue
        if not isinstance(payload, list) or not payload:
            summary[metric_key] = {"status": "no_data", "series_count": 0}
            continue

        latest_values: list[float] = []
        for series in payload:
            points = series.get("points") or []
            if not points:
                continue
            last = points[-1]
            value = last.get("value")
            if isinstance(value, (int, float)):
                latest_values.append(float(value))
            elif value is not None:
                try:
                    latest_values.append(float(value))
                except (TypeError, ValueError):
                    pass

        if not latest_values:
            summary[metric_key] = {
                "status": "no_points",
                "series_count": len(payload),
            }
            continue

        summary[metric_key] = {
            "status": "ok",
            "series_count": len(payload),
            "latest_value": max(latest_values),
            "min_latest": min(latest_values),
            "max_latest": max(latest_values),
        }
    return summary
