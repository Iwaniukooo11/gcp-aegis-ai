"""E2E tests for Query Processor incident routes.

Paths covered:
  GET /v1/incidents/latest
    - Returns formatted incident list with minutes_ago computed
    - Empty BigQuery result returns count=0
    - limit=0 → 400, limit=51 → 400
    - BigQuery failure → 500

  POST /v1/incidents/{id}/query
    - Full 3-step Gemini pipeline succeeds (metrics fetched)
    - Session not found → 404 with SESSION_NOT_FOUND code
    - Gemini metric plan failure → 500
    - Cloud Monitoring failure → degraded response still returned (metrics_fetched=False)
"""
from unittest.mock import patch

_METRIC_PLAN = {
    "metrics": [{"type": "memory_utilization"}],
    "rationale": "check memory trend",
    "window_minutes": 15,
}
_ANALYSIS = {
    "root_cause_candidates": ["Memory leak in request handler"],
    "confidence": "high",
    "additional_signals_needed": [],
}
_SLACK_TEXT = "*INC-2026-000042* Memory leak detected in java-api. Increase heap size."


class TestGetLatestIncidents:
    def test_returns_formatted_list_with_minutes_ago(self, client, qp_bq, sample_bq_rows):
        with patch.object(qp_bq, "get_latest_incidents", return_value=sample_bq_rows) as mock_query:
            resp = client.get("/v1/incidents/latest?limit=10")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["limit"] == 10
        assert body["incidents"][0]["incident_id"] == "INC-2026-000042"
        assert body["incidents"][0]["service_name"] == "java-api"
        assert "minutes_ago" in body["incidents"][0]
        mock_query.assert_called_once_with(limit=10)

    def test_empty_result_returns_zero_count(self, client, qp_bq):
        with patch.object(qp_bq, "get_latest_incidents", return_value=[]):
            resp = client.get("/v1/incidents/latest?limit=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["incidents"] == []

    def test_limit_zero_returns_400(self, client):
        resp = client.get("/v1/incidents/latest?limit=0")
        assert resp.status_code == 400

    def test_limit_above_max_returns_400(self, client):
        resp = client.get("/v1/incidents/latest?limit=51")
        assert resp.status_code == 400

    def test_bigquery_error_returns_500(self, client, qp_bq):
        with patch.object(qp_bq, "get_latest_incidents", side_effect=Exception("BQ unavailable")):
            resp = client.get("/v1/incidents/latest")

        assert resp.status_code == 500


class TestQueryIncident:
    def test_happy_path_full_pipeline_returns_slack_text(
        self, client, qp_firestore, qp_vertex, qp_monitoring, sample_session
    ):
        with patch.object(qp_firestore, "get_session", return_value=sample_session), \
             patch.object(qp_firestore, "append_messages"), \
             patch.object(qp_vertex, "plan_metrics", return_value=_METRIC_PLAN), \
             patch.object(qp_monitoring, "execute_plan", return_value={"kubernetes.io/container/memory/used_bytes": [{"points": []}]}), \
             patch.object(qp_vertex, "analyze_metrics", return_value=_ANALYSIS), \
             patch.object(qp_vertex, "format_slack_response", return_value=_SLACK_TEXT):
            resp = client.post(
                "/v1/incidents/INC-2026-000042/query",
                json={"text": "why is memory spiking"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["incident_id"] == "INC-2026-000042"
        assert body["slack_text"] == _SLACK_TEXT
        assert body["session_updated"] is True
        assert body["metrics_fetched"] is True
        assert "timestamp" in body
        assert "processing_ms" in body

    def test_session_not_found_returns_404(self, client, qp_firestore):
        with patch.object(qp_firestore, "get_session", return_value=None):
            resp = client.post(
                "/v1/incidents/INC-9999-999999/query",
                json={"text": "help"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"]["error_code"] == "SESSION_NOT_FOUND"
        assert resp.json()["detail"]["incident_id"] == "INC-9999-999999"

    def test_gemini_plan_failure_returns_500(self, client, qp_firestore, qp_vertex, sample_session):
        with patch.object(qp_firestore, "get_session", return_value=sample_session), \
             patch.object(qp_firestore, "append_messages"), \
             patch.object(qp_vertex, "plan_metrics", side_effect=RuntimeError("Vertex quota exceeded")):
            resp = client.post(
                "/v1/incidents/INC-2026-000042/query",
                json={"text": "what is wrong"},
            )

        assert resp.status_code == 500

    def test_monitoring_failure_still_returns_answer(
        self, client, qp_firestore, qp_vertex, qp_monitoring, sample_session
    ):
        """When Cloud Monitoring fails, QP continues with empty metric results."""
        degraded_analysis = {
            "root_cause_candidates": ["Unknown — no metric data available"],
            "confidence": "low",
            "additional_signals_needed": ["memory metrics"],
        }
        degraded_text = "Could not fetch metrics, but based on logs: possible memory leak."

        with patch.object(qp_firestore, "get_session", return_value=sample_session), \
             patch.object(qp_firestore, "append_messages"), \
             patch.object(qp_vertex, "plan_metrics", return_value=_METRIC_PLAN), \
             patch.object(qp_monitoring, "execute_plan", side_effect=Exception("Monitoring API down")), \
             patch.object(qp_vertex, "analyze_metrics", return_value=degraded_analysis), \
             patch.object(qp_vertex, "format_slack_response", return_value=degraded_text):
            resp = client.post(
                "/v1/incidents/INC-2026-000042/query",
                json={"text": "what is wrong"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["slack_text"] == degraded_text
        assert body["metrics_fetched"] is False
