"""Metric plan helpers: question-driven supplements and result summaries."""

from datetime import datetime, timezone

from app.integrations.metric_catalog import (
    GCP_METRIC_TYPE_BY_ID,
    GCP_METRIC_TYPE_TO_ID,
    METRIC_VALUE_KIND_BY_ID,
)
from app.integrations.vertex import _build_k8s_container_filter, _normalize_metric_item

_QUESTION_METRIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cpu", ("cpu_utilization", "cpu_core_usage", "cpu_request_utilization")),
    ("memory", ("memory_utilization", "memory_limit_utilization")),
    ("mem", ("memory_utilization", "memory_limit_utilization")),
    ("restart", ("pod_restart_count",)),
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

    for keyword, type_ids in _QUESTION_METRIC_KEYWORDS:
        if keyword not in q:
            continue
        for type_id in type_ids:
            if type_id in existing_types:
                continue
            spec = _normalize_metric_item({"type": type_id}, session, window)
            if spec is None:
                continue
            metrics.append(spec)
            existing_types.add(type_id)

    return {
        "metrics": metrics,
        "rationale": str(plan.get("rationale", "") or ""),
        "window_minutes": window,
    }


def parse_session_anchor(session: dict) -> datetime | None:
    """Return incident time from log_timestamp or session created_at for Monitoring lookback."""
    raw = session.get("log_timestamp") or session.get("created_at")
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
    if best is not None and best_delta is not None and best_delta <= 3600:
        return best
    return points[-1]


def _points_with_time_and_value(points: list[dict]) -> list[tuple[datetime, float]]:
    parsed = []
    for point in points:
        ts = _parse_point_time(point)
        value = _point_value(point)
        if ts is not None and value is not None:
            parsed.append((ts, value))
    return sorted(parsed, key=lambda item: item[0])


def _nearest_nonzero_point(points: list[dict], anchor: datetime | None) -> dict | None:
    nonzero = [point for point in points if (_point_value(point) or 0.0) > 0.0]
    return _point_nearest_anchor(nonzero, anchor)


def _average_cores_from_cumulative(points: list[dict], anchor: datetime | None) -> float | None:
    parsed = _points_with_time_and_value(points)
    if len(parsed) < 2:
        return None

    p2_index = len(parsed) - 1
    if anchor is not None:
        for index, (ts, _) in enumerate(parsed):
            if ts >= anchor:
                p2_index = max(index, 1)
                break

    t1, v1 = parsed[p2_index - 1]
    t2, v2 = parsed[p2_index]
    dt = (t2 - t1).total_seconds()
    if dt <= 0:
        return None
    return max(0.0, (v2 - v1) / dt)


def _sum_bytes_near_anchor(series_list: list[dict], anchor: datetime | None) -> float | None:
    total = 0.0
    samples = 0
    for series in series_list:
        points = series.get("points") or []
        point = _point_nearest_anchor(points, anchor)
        value = _point_value(point) if point else None
        if value == 0:
            nonzero_point = _nearest_nonzero_point(points, anchor)
            value = _point_value(nonzero_point) if nonzero_point else value
        if value is None:
            continue
        total += value
        samples += 1
    return total if samples else None


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

    if value_kind == "utilization_fraction":
        if incident_value is None:
            return {"status": "no_points", "type": type_id, "gcp_metric_type": gcp_metric}
        percent = round(incident_value * 100.0, 2)
        unit_by_type = {
            "cpu_utilization": "percent_of_cpu_limit",
            "cpu_request_utilization": "percent_of_cpu_request",
            "memory_limit_utilization": "percent_of_memory_limit",
        }
        display_unit_by_type = {
            "cpu_utilization": "container CPU limit",
            "cpu_request_utilization": "requested CPU",
            "memory_limit_utilization": "container memory limit",
        }
        display_unit = display_unit_by_type.get(type_id, "limit")
        return {
            "status": "ok",
            "type": type_id,
            "gcp_metric_type": gcp_metric,
            "utilization_fraction": round(incident_value, 4),
            "utilization_percent": percent,
            "unit": unit_by_type.get(type_id, "percent"),
            "display": f"{percent}% of {display_unit}",
        }

    if value_kind == "cumulative_cpu" or gcp_metric == _LEGACY_CUMULATIVE_CPU:
        cores = _average_cores_from_cumulative(all_points, anchor_time)
        if cores is not None:
            return {
                "status": "ok",
                "type": type_id,
                "gcp_metric_type": gcp_metric,
                "average_cores": round(cores, 4),
                "unit": "cores",
                "display": f"~{round(cores, 3)} cores (avg over last sample interval)",
            }
        return {
            "status": "no_rate",
            "type": type_id,
            "gcp_metric_type": gcp_metric,
            "series_count": len(series_list),
        }

    if value_kind == "bytes":
        used_bytes = _sum_bytes_near_anchor(series_list, anchor_time)
        if used_bytes is None:
            return {"status": "no_points", "type": type_id, "gcp_metric_type": gcp_metric}
        mib = used_bytes / (1024 * 1024)
        return {
            "status": "ok",
            "type": type_id,
            "gcp_metric_type": gcp_metric,
            "used_bytes": int(used_bytes),
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
    if "all metric" in q or "all metrics" in q:
        lines = []
        for type_id, entry in summary.items():
            if entry.get("status") == "ok" and entry.get("display"):
                lines.append(f"{type_id}: *{entry['display']}*")
        return "\n".join(lines) if lines else None

    lines: list[str] = []

    if "cpu" in q:
        cpu = next(
            (
                summary.get(type_id, {})
                for type_id in ("cpu_utilization", "cpu_request_utilization", "cpu_core_usage")
                if summary.get(type_id, {}).get("status") == "ok"
                and summary.get(type_id, {}).get("display")
            ),
            {},
        )
        if cpu.get("display"):
            lines.append(f"CPU near incident time: *{cpu['display']}*")
        else:
            lines.append("CPU near incident time: no Cloud Monitoring data in lookback window.")

    if "mem" in q or "memory" in q:
        mem = next(
            (
                summary.get(type_id, {})
                for type_id in ("memory_utilization", "memory_limit_utilization")
                if summary.get(type_id, {}).get("status") == "ok"
                and summary.get(type_id, {}).get("display")
            ),
            {},
        )
        if mem.get("display"):
            lines.append(f"Memory near incident time: *{mem['display']}*")
        else:
            lines.append("Memory near incident time: no Cloud Monitoring data in lookback window.")

    if "restart" in q:
        restarts = summary.get("pod_restart_count", {})
        if restarts.get("status") == "ok" and restarts.get("display") is not None:
            lines.append(f"Restarts at incident time: *{restarts['display']}*")

    return "\n".join(lines) if lines else None
