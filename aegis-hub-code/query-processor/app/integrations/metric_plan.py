"""Metric plan helpers: question-driven supplements and result summaries."""

from datetime import datetime, timezone

from app.integrations.metric_catalog import (
    GCP_METRIC_TYPE_BY_ID,
    GCP_METRIC_TYPE_TO_ID,
    METRIC_VALUE_KIND_BY_ID,
)
from app.integrations.vertex import _build_k8s_container_filter, _normalize_metric_item

_QUESTION_METRIC_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("cpu", "cpu_utilization"),
    ("memory", "memory_utilization"),
    ("mem", "memory_utilization"),
    ("restart", "pod_restart_count"),
)

_LEGACY_CUMULATIVE_CPU = "kubernetes.io/container/cpu/core_usage_time"


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


def _parse_point_time(point: dict) -> datetime | None:
    raw = point.get("end_time") or point.get("start_time")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _point_value(point: dict) -> float | None:
    value = point.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _point_nearest_anchor(points: list[dict], anchor: datetime | None) -> dict | None:
    if not points:
        return None
    if anchor is None:
        return points[-1]
    best: dict | None = None
    best_delta = None
    for point in points:
        ts = _parse_point_time(point)
        if ts is None:
            continue
        delta = abs((ts - anchor).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = point
    return best or points[-1]


def _average_cores_from_cumulative(points: list[dict]) -> float | None:
    if len(points) < 2:
        return None
    p1, p2 = points[-2], points[-1]
    v1, v2 = _point_value(p1), _point_value(p2)
    t1, t2 = _parse_point_time(p1), _parse_point_time(p2)
    if v1 is None or v2 is None or t1 is None or t2 is None:
        return None
    dt = (t2 - t1).total_seconds()
    if dt <= 0:
        return None
    return max(0.0, (v2 - v1) / dt)


def _summarize_series(
    type_id: str,
    gcp_metric: str,
    series_list: list[dict],
    anchor_time: datetime | None,
) -> dict:
    value_kind = METRIC_VALUE_KIND_BY_ID.get(type_id, "counter")
    all_points: list[dict] = []
    for series in series_list:
        all_points.extend(series.get("points") or [])

    if not all_points:
        return {
            "status": "no_points",
            "type": type_id,
            "gcp_metric_type": gcp_metric,
            "series_count": len(series_list),
        }

    incident_point = _point_nearest_anchor(all_points, anchor_time)
    incident_value = _point_value(incident_point) if incident_point else None

    if value_kind == "cpu_limit_fraction":
        if incident_value is None:
            return {"status": "no_points", "type": type_id, "gcp_metric_type": gcp_metric}
        percent = round(incident_value * 100.0, 2)
        return {
            "status": "ok",
            "type": type_id,
            "gcp_metric_type": gcp_metric,
            "utilization_fraction": round(incident_value, 4),
            "utilization_percent": percent,
            "unit": "percent_of_cpu_limit",
            "display": f"{percent}% of container CPU limit",
        }

    if gcp_metric == _LEGACY_CUMULATIVE_CPU:
        cores = _average_cores_from_cumulative(all_points)
        if cores is not None:
            return {
                "status": "ok",
                "type": type_id,
                "gcp_metric_type": gcp_metric,
                "average_cores": round(cores, 4),
                "unit": "cores",
                "display": f"~{round(cores, 3)} cores (avg over last sample interval)",
            }

    if value_kind == "bytes" and incident_value is not None:
        mib = incident_value / (1024 * 1024)
        return {
            "status": "ok",
            "type": type_id,
            "gcp_metric_type": gcp_metric,
            "used_bytes": int(incident_value),
            "used_mib": round(mib, 2),
            "unit": "bytes",
            "display": f"{round(mib, 1)} MiB",
        }

    if incident_value is not None:
        return {
            "status": "ok",
            "type": type_id,
            "gcp_metric_type": gcp_metric,
            "latest_value": incident_value,
            "unit": "counter",
            "display": str(int(incident_value) if incident_value == int(incident_value) else incident_value),
        }

    return {"status": "no_points", "type": type_id, "gcp_metric_type": gcp_metric}


def summarize_metric_results(
    metric_results: dict,
    anchor_time: datetime | None = None,
) -> dict:
    """Build type-keyed summaries with correct units for Slack formatting."""
    summary: dict = {}
    for metric_key, payload in metric_results.items():
        if isinstance(payload, dict) and payload.get("error"):
            type_id = GCP_METRIC_TYPE_TO_ID.get(metric_key, metric_key)
            summary[type_id] = {
                "status": "error",
                "type": type_id,
                "detail": payload["error"],
            }
            continue
        if not isinstance(payload, list) or not payload:
            type_id = GCP_METRIC_TYPE_TO_ID.get(metric_key, metric_key)
            summary[type_id] = {
                "status": "no_data",
                "type": type_id,
                "series_count": 0,
            }
            continue

        type_id = GCP_METRIC_TYPE_TO_ID.get(metric_key, metric_key)
        summary[type_id] = _summarize_series(type_id, metric_key, payload, anchor_time)
    return summary


def format_metric_facts_line(question: str, summary: dict) -> str | None:
    """Deterministic metric sentence so Slack does not misread cumulative counters."""
    q = question.lower()
    lines: list[str] = []

    if "cpu" in q:
        cpu = summary.get("cpu_utilization", {})
        if cpu.get("status") == "ok" and cpu.get("display"):
            lines.append(f"CPU at incident time: *{cpu['display']}*")
        elif cpu.get("status") in ("no_data", "no_points", "error"):
            lines.append("CPU at incident time: no Monitoring data in lookback window.")

    if "mem" in q or "memory" in q:
        mem = summary.get("memory_utilization", {})
        if mem.get("status") == "ok" and mem.get("display"):
            lines.append(f"Memory at incident time: *{mem['display']}*")

    if "restart" in q:
        restarts = summary.get("pod_restart_count", {})
        if restarts.get("status") == "ok" and restarts.get("display") is not None:
            lines.append(f"Restarts at incident time: *{restarts['display']}*")

    return "\n".join(lines) if lines else None
