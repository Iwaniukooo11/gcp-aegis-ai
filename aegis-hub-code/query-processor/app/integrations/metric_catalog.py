"""Allowlisted Cloud Monitoring metrics the Query Processor can fetch."""

from typing import TypedDict


class FetchMetricSpec(TypedDict):
    type: str
    gcp_metric_type: str
    description: str


ALLOWED_FETCH_METRICS: tuple[FetchMetricSpec, ...] = (
    {
        "type": "cpu_utilization",
        "gcp_metric_type": "kubernetes.io/container/cpu/core_usage_time",
        "description": "Container CPU usage (GKE k8s_container)",
    },
    {
        "type": "memory_utilization",
        "gcp_metric_type": "kubernetes.io/container/memory/used_bytes",
        "description": "Container memory used bytes (GKE k8s_container)",
    },
    {
        "type": "pod_restart_count",
        "gcp_metric_type": "kubernetes.io/container/restart_count",
        "description": "Container restart count (GKE k8s_container)",
    },
)

ALLOWED_METRIC_TYPE_IDS: tuple[str, ...] = tuple(m["type"] for m in ALLOWED_FETCH_METRICS)

GCP_METRIC_TYPE_BY_ID: dict[str, str] = {
    m["type"]: m["gcp_metric_type"] for m in ALLOWED_FETCH_METRICS
}

METRIC_PLAN_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "window_minutes": {
            "type": "INTEGER",
            "description": "Lookback window in minutes (5-60).",
        },
        "metrics": {
            "type": "ARRAY",
            "description": "Metrics to fetch; use only allowlisted type ids.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {
                        "type": "STRING",
                        "enum": list(ALLOWED_METRIC_TYPE_IDS),
                        "description": "Allowlisted metric id.",
                    },
                },
                "required": ["type"],
            },
        },
        "rationale": {
            "type": "STRING",
            "description": "Short explanation of why these metrics were chosen.",
        },
    },
    "required": ["window_minutes", "metrics", "rationale"],
}


def allowed_metrics_for_prompt() -> list[dict]:
    """Return catalog entries suitable for embedding in a Gemini prompt."""
    return [
        {
            "type": m["type"],
            "gcp_metric_type": m["gcp_metric_type"],
            "description": m["description"],
        }
        for m in ALLOWED_FETCH_METRICS
    ]
