"""Tests for Query Processor BigQuery incident reads."""

from unittest.mock import patch


class _FakeJob:
    def result(self):
        return [
            {
                "incident_id": "INC-2026-000042",
                "service_name": "java-api",
                "client_project_id": "mock-client-dev",
                "severity": "ERROR",
                "error_type": "OutOfMemoryError",
                "short_message": "Java heap space",
                "ai_summary": "Heap exhausted.",
                "created_at": "2026-05-21T00:00:00+00:00",
            }
        ]


class _FakeClient:
    def __init__(self):
        self.query_text = ""
        self.job_config = None

    def query(self, query, job_config):
        self.query_text = query
        self.job_config = job_config
        return _FakeJob()


def test_latest_incidents_query_excludes_legacy_non_application_noise(qp_bq):
    fake_client = _FakeClient()

    with patch.object(qp_bq, "_get_client", return_value=fake_client):
        rows = qp_bq.get_latest_incidents(limit=5)

    assert rows[0]["incident_id"] == "INC-2026-000042"
    assert "terminal_status = 'SUCCESS'" in fake_client.query_text
    assert "severity IN ('ERROR', 'CRITICAL', 'ALERT', 'EMERGENCY')" in fake_client.query_text
    assert "error_type IS NOT NULL" in fake_client.query_text
    assert "TRIM(error_type) != ''" in fake_client.query_text
    assert "k8s-pod/app_kubernetes_io/part-of" in fake_client.query_text
    assert "service_name IN ('java-api', 'python-api', 'python-worker')" in fake_client.query_text
    assert "QUALIFY ROW_NUMBER()" in fake_client.query_text
