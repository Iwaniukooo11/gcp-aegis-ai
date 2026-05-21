"""Cloud Monitoring time-series executor for Query Processor.

Takes a MetricFetchPlan from Gemini step 1 and queries the client project's
Monitoring API. Returns a MetricResults dict ready to pass to Gemini step 2.

Only projects in ALLOWED_CLIENT_PROJECT_IDS may be queried.
"""
import logging
from datetime import datetime, timedelta, timezone

from google.cloud import monitoring_v3

from app.config import get_settings

logger = logging.getLogger(__name__)


def execute_plan(client_project_id: str, plan: dict) -> dict:
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
        metric_type = metric_spec.get("metric_type", "")
        extra_filter = metric_spec.get("filter", "")
        window_minutes = int(metric_spec.get("window_minutes", 30))

        end_time = datetime.now(tz=timezone.utc)
        start_time = end_time - timedelta(minutes=window_minutes)

        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": int(end_time.timestamp())},
                "start_time": {"seconds": int(start_time.timestamp())},
            }
        )

        filter_str = f'metric.type="{metric_type}"'
        if extra_filter:
            filter_str += f" AND {extra_filter}"

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
        except Exception as exc:
            logger.warning("Failed to fetch metric %s: %s", metric_type, exc)
            results[metric_type] = {"error": str(exc)}

    return results


def _serialize_series(series_list: list) -> list[dict]:
    """Convert Monitoring API series objects to plain dicts."""
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
                    "value": (
                        value.double_value
                        or value.int64_value
                        or value.bool_value
                        or str(value.string_value)
                    ),
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
