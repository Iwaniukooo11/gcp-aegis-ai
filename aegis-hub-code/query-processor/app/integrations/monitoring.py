"""Cloud Monitoring time-series executor for Query Processor."""
import logging
from datetime import datetime, timedelta, timezone

from google.cloud import monitoring_v3

from app.config import get_settings
from app.integrations.metric_catalog import GCP_METRIC_TYPE_BY_ID
from app.integrations.vertex import build_k8s_container_filter

logger = logging.getLogger(__name__)

_ALLOWED_GCP_METRIC_TYPES = frozenset(GCP_METRIC_TYPE_BY_ID.values())
_MAX_LOOKBACK = timedelta(days=7)


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
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(minutes=window_minutes)
    if anchor_time is not None:
        if anchor_time.tzinfo is None:
            anchor_time = anchor_time.replace(tzinfo=timezone.utc)
        anchor_start = anchor_time - timedelta(minutes=window_minutes)
        if anchor_start < start_time:
            start_time = anchor_start
    if end_time - start_time > _MAX_LOOKBACK:
        start_time = end_time - _MAX_LOOKBACK
    return monitoring_v3.TimeInterval(
        {
            "end_time": {"seconds": int(end_time.timestamp())},
            "start_time": {"seconds": int(start_time.timestamp())},
        }
    )


def _build_time_series_filter(metric_type: str, extra_filter: str) -> str | None:
    metric_type = metric_type.strip()
    if not metric_type:
        return None
    extra = extra_filter.strip()
    if extra and "metric.type=" in extra:
        return extra
    base = f'metric.type="{metric_type}"'
    return f"{base} AND {extra}" if extra else base


def execute_plan(
    client_project_id: str,
    plan: dict,
    anchor_time: datetime | None = None,
) -> dict:
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
            logger.warning("Skipping non-allowlisted metric: %s", metric_spec)
            continue
        extra_filter = str(metric_spec.get("filter") or "")
        try:
            window_minutes = int(metric_spec.get("window_minutes", 30))
        except (TypeError, ValueError):
            window_minutes = 30

        filter_str = _build_time_series_filter(metric_type, extra_filter)
        if filter_str is None:
            continue

        interval = _query_interval(anchor_time, window_minutes)

        try:
            series_list = list(
                client.list_time_series(
                    request={
                        "name": project_name,
                        "filter": filter_str,
                        "interval": interval,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    }
                )
            )
            results[metric_type] = _serialize_series(series_list)
            if not series_list:
                logger.warning("No time series for %s", metric_type)
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", metric_type, exc)
            results[metric_type] = {"error": str(exc)}

    return results


def _serialize_series(series_list: list) -> list[dict]:
    output = []
    for series in series_list:
        points = []
        for point in series.points:
            interval = point.interval
            value = point.value
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
