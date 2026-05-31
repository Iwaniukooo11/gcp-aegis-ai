"""Allowlisted Cloud Monitoring metrics the Query Processor can fetch."""

from typing import Literal, TypedDict

MetricValueKind = Literal[
    "utilization_fraction",
    "bytes",
    "counter",
    "cumulative_cpu",
]


class FetchMetricSpec(TypedDict):
    type: str
    gcp_metric_type: str
    description: str
    value_kind: MetricValueKind


ALLOWED_FETCH_METRICS: tuple[FetchMetricSpec, ...] = (
    {
        "type": "cpu_utilization",
        "gcp_metric_type": "kubernetes.io/container/cpu/limit_utilization",
        "value_kind": "utilization_fraction",
        "description": "Fraction of container CPU limit in use (0.0–1.0, GKE k8s_container)",
    },
    {
        "type": "cpu_core_usage",
        "gcp_metric_type": "kubernetes.io/container/cpu/core_usage_time",
        "value_kind": "cumulative_cpu",
        "description": "Cumulative container CPU time; summarized as average cores over the last sample interval",
    },
    {
        "type": "cpu_request_utilization",
        "gcp_metric_type": "kubernetes.io/container/cpu/request_utilization",
        "value_kind": "utilization_fraction",
        "description": "Fraction of requested CPU in use (0.0–1.0, GKE k8s_container)",
    },
    {
        "type": "memory_utilization",
        "gcp_metric_type": "kubernetes.io/container/memory/used_bytes",
        "value_kind": "bytes",
        "description": "Container memory used in bytes (GKE k8s_container)",
    },
    {
        "type": "memory_limit_utilization",
        "gcp_metric_type": "kubernetes.io/container/memory/limit_utilization",
        "value_kind": "utilization_fraction",
        "description": "Fraction of container memory limit in use (0.0–1.0, GKE k8s_container)",
    },
    {
        "type": "pod_restart_count",
        "gcp_metric_type": "kubernetes.io/container/restart_count",
        "value_kind": "counter",
        "description": "Container restart count (GKE k8s_container)",
    },
)

ALLOWED_METRIC_TYPE_IDS: tuple[str, ...] = tuple(m["type"] for m in ALLOWED_FETCH_METRICS)

GCP_METRIC_TYPE_BY_ID: dict[str, str] = {
    m["type"]: m["gcp_metric_type"] for m in ALLOWED_FETCH_METRICS
}

GCP_METRIC_TYPE_TO_ID: dict[str, str] = {
    m["gcp_metric_type"]: m["type"] for m in ALLOWED_FETCH_METRICS
}

METRIC_VALUE_KIND_BY_ID: dict[str, MetricValueKind] = {
    m["type"]: m["value_kind"] for m in ALLOWED_FETCH_METRICS
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
            "value_kind": m["value_kind"],
            "description": m["description"],
        }
        for m in ALLOWED_FETCH_METRICS
    ]
