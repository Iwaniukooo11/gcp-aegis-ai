"""Cloud Monitoring time-series executor for Query Processor.

Takes a MetricFetchPlan from Gemini step 1 and queries the client project's
Monitoring API. Returns a MetricResults dict ready to pass to Gemini step 2.

Only projects in ALLOWED_CLIENT_PROJECT_IDS may be queried.
"""
import logging
from datetime import datetime, timedelta, timezone

from google.cloud import monitoring_v3

from app.config import get_settings
from app.integrations.metric_catalog import GCP_METRIC_TYPE_BY_ID

logger = logging.getLogger(__name__)

_ALLOWED_GCP_METRIC_TYPES = frozenset(GCP_METRIC_TYPE_BY_ID.values())
_ANCHOR_AFTER_BUFFER = timedelta(minutes=5)


def _build_time_series_filter(metric_type: str, extra_filter: str) -> str | None:
    metric_type = metric_type.strip()
    if not metric_type:
        return None
    extra = extra_filter.strip()
    if extra and "metric.type=" in extra:
        return extra
    base = f'metric.type="{metric_type}"'
    return f"{base} AND {extra}" if extra else base


def _relax_cluster_filter(filter_str: str) -> str:
    parts = [
        p
        for p in filter_str.split(" AND ")
        if p and not p.startswith('resource.labels.cluster_name=')
    ]
    return " AND ".join(parts)


def _point_value(point) -> float | int | bool | str | None:
    value = point.value
    if value is None:
        return None
    field = value._pb.WhichOneof("value")
    if not field:
        return None
    return getattr(value, field)


def _query_interval(
    anchor_time: datetime | None,
    window_minutes: int,
) -> monitoring_v3.TimeInterval:
    now = datetime.now(tz=timezone.utc)
    if anchor_time is None:
        end_time = now
        start_time = end_time - timedelta(minutes=window_minutes)
    else:
        if anchor_time.tzinfo is None:
            anchor_time = anchor_time.replace(tzinfo=timezone.utc)
        end_time = min(now, anchor_time + _ANCHOR_AFTER_BUFFER)
        start_time = anchor_time - timedelta(minutes=window_minutes)

    return monitoring_v3.TimeInterval(
        {
            "end_time": {"seconds": int(end_time.timestamp())},
            "start_time": {"seconds": int(start_time.timestamp())},
        }
    )


def execute_plan(
    client_project_id: str,
    plan: dict,
    anchor_time: datetime | None = None,
) -> dict:
    """Fetch metric time-series for each item in MetricFetchPlan.metrics.

    Returns a dict keyed by metric_type with a list of data points per series.
    Raises ValueError if client_project_id is not in the allowlist.
    """
    s = get_settings()
    allowed = s.allowed_projects()
    if allowed and client_project_id not in allowed:
        raise ValueError(f"Project {client_project_id} not in allowlist")

    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{client_project_id}"
    results: dict = {}

    for metric_spec in plan.get("metrics", []):
        if not isinstance(metric_spec, dict):
            continue
        metric_type = str(metric_spec.get("metric_type") or "").strip()
        if metric_type not in _ALLOWED_GCP_METRIC_TYPES:
            logger.warning("Skipping non-allowlisted metric_type: %s", metric_spec)
            continue
        extra_filter = str(metric_spec.get("filter") or "")
        try:
            window_minutes = int(metric_spec.get("window_minutes", 30))
        except (TypeError, ValueError):
            window_minutes = 30

        filter_str = _build_time_series_filter(metric_type, extra_filter)
        if filter_str is None:
            logger.warning("Skipping metric spec without metric_type: %s", metric_spec)
            continue

        interval = _query_interval(anchor_time, window_minutes)

        result_key = metric_type or filter_str

        try:
            series_list = _list_series(client, project_name, filter_str, interval)
            if not series_list and 'resource.labels.cluster_name=' in filter_str:
                relaxed = _relax_cluster_filter(filter_str)
                if relaxed != filter_str:
                    logger.info(
                        "Retrying metric %s without cluster_name filter",
                        result_key,
                    )
                    series_list = _list_series(client, project_name, relaxed, interval)
            results[result_key] = _serialize_series(series_list)
            if not series_list:
                logger.warning("No time series for metric %s (filter=%s)", result_key, filter_str)
        except Exception as exc:
            logger.warning("Failed to fetch metric %s: %s", result_key, exc)
            results[result_key] = {"error": str(exc)}

    return results


def _list_series(
    client: monitoring_v3.MetricServiceClient,
    project_name: str,
    filter_str: str,
    interval: monitoring_v3.TimeInterval,
) -> list:
    return list(
        client.list_time_series(
            request={
                "name": project_name,
                "filter": filter_str,
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )
    )


def _serialize_series(series_list: list) -> list[dict]:
    """Convert Monitoring API series objects to plain dicts."""
    output = []
    for series in series_list:
        points = []
        for point in series.points:
            interval = point.interval
            points.append(
                {
                    "start_time": interval.start_time.isoformat() if interval.start_time else None,
                    "end_time": interval.end_time.isoformat() if interval.end_time else None,
                    "value": _point_value(point),
                }
            )
        output.append(
            {
                "metric": dict(series.metric.labels),
                "resource": dict(series.resource.labels),
                "points": points[-20:],
            }
        )
    return output
