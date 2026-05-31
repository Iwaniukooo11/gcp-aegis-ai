"""Shared test fixtures and sample data for all Aegis Hub e2e tests.

These fixtures are available to every test in every sub-package because
pytest automatically includes fixtures from parent conftest.py files.
"""
import base64
import copy
import json

import pytest


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_LOG_ENTRY: dict = {
    "insertId": "abc123insertid",
    "logName": "projects/mock-client-dev/logs/stderr",
    "resource": {
        "type": "k8s_container",
        "labels": {
            "project_id": "mock-client-dev",
            "cluster_name": "mock-gke-autopilot",
            "namespace_name": "default",
            "container_name": "java-api",
            "pod_name": "java-api-abc123",
        },
    },
    "severity": "ERROR",
    "textPayload": (
        "java.lang.OutOfMemoryError: Java heap space\n"
        "\tat java.base/java.util.Arrays.copyOf(Arrays.java:3745)\n"
        "\tat com.example.api.Service.processRequest(Service.java:88)"
    ),
    "jsonPayload": {
        "severity": "ERROR",
        "message": "Java heap space",
        "client_project_id": "mock-client-dev",
        "service_name": "java-api",
        "environment": "test",
        "scenario": "JAVA_OUT_OF_MEMORY",
        "error_type": "OutOfMemoryError",
        "incident_candidate": True,
        "correlation_id": "test-correlation-id",
        "team": "demo",
        "http_method": "GET",
        "path": "/chaos/oom",
        "status_code": 500,
        "duration_ms": 42.0,
        "stack_trace_preview": "java.lang.OutOfMemoryError: Java heap space",
    },
    "timestamp": "2026-05-21T00:00:00Z",
    "labels": {"k8s-pod/app": "java-api"},
}

SAMPLE_SESSION: dict = {
    "incident_id": "INC-2026-000042",
    "client_project_id": "mock-client-dev",
    "service_name": "java-api",
    "cluster_name": "mock-gke-autopilot",
    "namespace": "default",
    "pod_name": "java-api-abc123",
    "severity": "ERROR",
    "error_type": "OutOfMemoryError",
    "ai_summary": "Java heap exhausted due to unbounded request processing.",
    "messages": [
        {
            "role": "model",
            "content": (
                "Incident INC-2026-000042: java-api reported OutOfMemoryError. "
                "Initial AI summary: Java heap exhausted."
            ),
        }
    ],
    "created_at": "2026-05-21T00:00:00Z",
    "log_timestamp": "2026-05-21T00:00:00Z",
    "updated_at": "2026-05-21T00:00:00Z",
    "ttl": "2026-05-22T00:00:00Z",
}

SAMPLE_BQ_ROWS: list[dict] = [
    {
        "incident_id": "INC-2026-000042",
        "service_name": "java-api",
        "client_project_id": "mock-client-dev",
        "severity": "ERROR",
        "error_type": "OutOfMemoryError",
        "short_message": "Java heap space",
        "ai_summary": "Heap exhausted.",
        "created_at": "2026-05-21T00:00:00+00:00",
    },
    {
        "incident_id": "INC-2026-000041",
        "service_name": "python-worker",
        "client_project_id": "mock-client-dev",
        "severity": "ERROR",
        "error_type": "TimeoutError",
        "short_message": "Worker timeout",
        "ai_summary": "Request timed out.",
        "created_at": "2026-05-20T23:00:00+00:00",
    },
]


def make_pubsub_envelope(log_entry: dict) -> dict:
    """Wrap a log entry dict in a Pub/Sub HTTP push envelope."""
    data_b64 = base64.b64encode(json.dumps(log_entry).encode()).decode()
    return {
        "message": {
            "data": data_b64,
            "messageId": "msg-001",
            "publishTime": "2026-05-21T00:00:00Z",
            "attributes": {},
        },
        "subscription": "projects/aegis-hub/subscriptions/aegis-analyzer-sub",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_log_entry() -> dict:
    return copy.deepcopy(SAMPLE_LOG_ENTRY)


@pytest.fixture
def sample_pubsub_envelope(sample_log_entry: dict) -> dict:
    return make_pubsub_envelope(sample_log_entry)


@pytest.fixture
def sample_session() -> dict:
    return SAMPLE_SESSION.copy()


@pytest.fixture
def sample_bq_rows() -> list[dict]:
    return [row.copy() for row in SAMPLE_BQ_ROWS]
