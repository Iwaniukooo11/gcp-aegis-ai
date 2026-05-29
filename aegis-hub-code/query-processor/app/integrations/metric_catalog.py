"""Hardcoded GKE container metrics Gemini may request."""

from typing import Literal, TypedDict

MetricValueKind = Literal[
    "cpu_limit_fraction",
    "bytes",
    "counter",
]

ALLOWED_FETCH_METRICS: tuple[dict, ...] = (
    {
        "type": "cpu_utilization",
        "gcp_metric_type": "kubernetes.io/container/cpu/limit_utilization",
        "value_kind": "cpu_limit_fraction",
        "description": "CPU use as fraction of container limit (0–1)",
    },
    {
        "type": "cpu_core_usage",
        "gcp_metric_type": "kubernetes.io/container/cpu/core_usage_time",
        "value_kind": "counter",
        "description": "Cumulative CPU time (rate → cores)",
    },
    {
        "type": "cpu_request_utilization",
        "gcp_metric_type": "kubernetes.io/container/cpu/request_utilization",
        "value_kind": "cpu_limit_fraction",
        "description": "CPU use as fraction of request (0–1)",
    },
    {
        "type": "memory_utilization",
        "gcp_metric_type": "kubernetes.io/container/memory/used_bytes",
        "value_kind": "bytes",
        "description": "Memory used (bytes)",
    },
    {
        "type": "memory_limit_utilization",
        "gcp_metric_type": "kubernetes.io/container/memory/limit_utilization",
        "value_kind": "cpu_limit_fraction",
        "description": "Memory use as fraction of limit (0–1)",
    },
    {
        "type": "pod_restart_count",
        "gcp_metric_type": "kubernetes.io/container/restart_count",
        "value_kind": "counter",
        "description": "Container restart count",
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
            "description": "Metrics to fetch from the hardcoded allowlist.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {
                        "type": "STRING",
                        "enum": list(ALLOWED_METRIC_TYPE_IDS),
                    },
                },
                "required": ["type"],
            },
        },
        "rationale": {"type": "STRING"},
    },
    "required": ["window_minutes", "metrics", "rationale"],
}


def allowed_metrics_for_prompt() -> list[dict]:
    return [
        {
            "type": m["type"],
            "gcp_metric_type": m["gcp_metric_type"],
            "value_kind": m["value_kind"],
            "description": m["description"],
        }
        for m in ALLOWED_FETCH_METRICS
    ]
