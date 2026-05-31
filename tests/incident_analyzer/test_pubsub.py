"""E2E tests for POST /pubsub/push.

Covered behavior:
  - first delivery creates receipt, session, Slack alert, and BigQuery row
  - completed duplicate delivery is skipped
  - incomplete receipts resume missing downstream work
  - retry-required failures return 500 for Pub/Sub retry
"""
import base64
import json
from unittest.mock import patch

_NORMALIZED = {
    "error_type": "OutOfMemoryError",
    "short_message": "Java heap space",
    "stack_trace_preview": "java.lang.OutOfMemoryError: Java heap space\n\tat java.util.Arrays.copyOf",
    "service_name": "java-api",
    "severity": "ERROR",
}

_CLASSIFICATION = {
    "ai_summary": "Heap exhausted by unbounded request processing.",
    "ai_recommendation": "Increase JVM heap limits and review for memory leaks.",
}

_FORMATTED_ALERT = "*INC-TEST* - java-api | ERROR | OutOfMemoryError\nAI: Heap exhausted."


def _envelope_for(log_entry: dict) -> dict:
    data_b64 = base64.b64encode(json.dumps(log_entry).encode()).decode()
    return {
        "message": {
            "data": data_b64,
            "messageId": "msg-ignored",
            "publishTime": "2026-05-21T00:00:00Z",
            "attributes": {},
        },
        "subscription": "projects/aegis-hub/subscriptions/test-sub",
    }


def _completed_receipt() -> dict:
    return {
        "incident_id": "INC-2026-000042",
        "analysis_completed": True,
        "bigquery_persisted": True,
        "session_created": True,
        "slack_handoff_succeeded": True,
        "slack_channel": "C_TEST_ALERTS",
        "slack_message_ts": "1.1",
        "first_alert_sent_at": "2026-05-21T00:00:01+00:00",
    }


def _analysis_receipt(**overrides: object) -> dict:
    receipt = {
        "incident_id": "INC-2026-000042",
        "analysis_completed": True,
        "normalized": _NORMALIZED,
        "classification": _CLASSIFICATION,
        "formatted_message": _FORMATTED_ALERT,
        "terminal_status": "SUCCESS",
        "terminal_failure_reason": "",
        "bigquery_persisted": False,
        "session_created": True,
        "slack_handoff_succeeded": True,
        "slack_channel": "C_TEST_ALERTS",
        "slack_message_ts": "1.1",
        "first_alert_sent_at": "2026-05-21T00:00:01+00:00",
    }
    receipt.update(overrides)
    return receipt


class TestPubSubPush:
    def test_full_success_pipeline_returns_success_status(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt", return_value=True), \
             patch.object(ia_firestore, "update_receipt") as mock_update_receipt, \
             patch.object(ia_firestore, "create_session") as mock_create_session, \
             patch.object(ia_vertex, "normalize_log", return_value=_NORMALIZED), \
             patch.object(ia_vertex, "classify_incident", return_value=_CLASSIFICATION), \
             patch.object(ia_vertex, "format_slack_alert", return_value=_FORMATTED_ALERT), \
             patch.object(ia_bq, "incident_exists_by_idempotency_key", return_value=False), \
             patch.object(ia_bq, "insert_incident") as mock_insert_incident, \
             patch.object(ia_sg_client, "post_alert", return_value={"ok": True, "ts": "1.1"}):
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUCCESS"
        assert body["incident_id"].startswith("INC-")
        mock_create_session.assert_called_once()
        mock_insert_incident.assert_called_once()
        row = mock_insert_incident.call_args.args[0]
        assert row["slack_channel"] == "C_TEST_ALERTS"
        assert row["slack_message_ts"] == "1.1"
        assert row["terminal_status"] == "SUCCESS"
        assert mock_insert_incident.call_args.kwargs["insert_id"]
        updates = [call.args[1] for call in mock_update_receipt.call_args_list]
        assert any(update.get("analysis_completed") is True for update in updates)
        assert any(update.get("session_created") is True for update in updates)
        assert any(update.get("slack_handoff_succeeded") is True for update in updates)
        assert any(update.get("bigquery_persisted") is True for update in updates)

    def test_completed_duplicate_delivery_skipped(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        with patch.object(ia_firestore, "get_receipt", return_value=_completed_receipt()), \
             patch.object(ia_vertex, "normalize_log") as mock_vertex, \
             patch.object(ia_bq, "insert_incident") as mock_bq, \
             patch.object(ia_sg_client, "post_alert") as mock_sg:
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"
        mock_vertex.assert_not_called()
        mock_bq.assert_not_called()
        mock_sg.assert_not_called()

    def test_incomplete_receipt_resumes_bigquery_without_reposting_slack(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        receipt = _analysis_receipt(bigquery_persisted=False)
        with patch.object(ia_firestore, "get_receipt", return_value=receipt), \
             patch.object(ia_firestore, "update_receipt") as mock_update_receipt, \
             patch.object(ia_vertex, "normalize_log") as mock_vertex, \
             patch.object(ia_bq, "incident_exists_by_idempotency_key", return_value=False), \
             patch.object(ia_bq, "insert_incident") as mock_insert_incident, \
             patch.object(ia_sg_client, "post_alert") as mock_sg:
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 200
        assert resp.json()["incident_id"] == "INC-2026-000042"
        mock_vertex.assert_not_called()
        mock_sg.assert_not_called()
        mock_insert_incident.assert_called_once()
        row = mock_insert_incident.call_args.args[0]
        assert row["slack_message_ts"] == "1.1"
        assert row["first_alert_sent_at"] == "2026-05-21T00:00:01+00:00"
        assert {"bigquery_persisted": True} in [call.args[1] for call in mock_update_receipt.call_args_list]

    def test_undecodeable_payload_acked_not_crashed(self, client):
        bad_envelope = {
            "message": {
                "data": "THIS_IS_NOT_VALID_BASE64_OR_JSON!!!",
                "messageId": "bad-msg-001",
                "publishTime": "2026-05-21T00:00:00Z",
                "attributes": {},
            },
            "subscription": "projects/aegis-hub/subscriptions/test-sub",
        }
        resp = client.post("/pubsub/push", json=bad_envelope)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ack_bad_payload"

    def test_non_candidate_error_log_is_ignored_before_receipt(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_log_entry
    ):
        sample_log_entry["jsonPayload"]["incident_candidate"] = False
        with patch.object(ia_firestore, "get_receipt") as mock_get_receipt, \
             patch.object(ia_vertex, "normalize_log") as mock_vertex, \
             patch.object(ia_bq, "insert_incident") as mock_bq, \
             patch.object(ia_sg_client, "post_alert") as mock_sg:
            resp = client.post("/pubsub/push", json=_envelope_for(sample_log_entry))

        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "not_incident_candidate"}
        mock_get_receipt.assert_not_called()
        mock_vertex.assert_not_called()
        mock_bq.assert_not_called()
        mock_sg.assert_not_called()

    def test_info_candidate_log_is_ignored_before_receipt(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_log_entry
    ):
        sample_log_entry["severity"] = "INFO"
        sample_log_entry["jsonPayload"]["severity"] = "INFO"
        with patch.object(ia_firestore, "get_receipt") as mock_get_receipt, \
             patch.object(ia_vertex, "normalize_log") as mock_vertex, \
             patch.object(ia_bq, "insert_incident") as mock_bq, \
             patch.object(ia_sg_client, "post_alert") as mock_sg:
            resp = client.post("/pubsub/push", json=_envelope_for(sample_log_entry))

        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored", "reason": "severity_below_error"}
        mock_get_receipt.assert_not_called()
        mock_vertex.assert_not_called()
        mock_bq.assert_not_called()
        mock_sg.assert_not_called()

    def test_gemini_failure_results_in_partial_success(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt", return_value=True), \
             patch.object(ia_firestore, "update_receipt"), \
             patch.object(ia_firestore, "create_session"), \
             patch.object(ia_vertex, "normalize_log", side_effect=Exception("Vertex quota exceeded")), \
             patch.object(ia_bq, "incident_exists_by_idempotency_key", return_value=False), \
             patch.object(ia_bq, "insert_incident") as mock_bq, \
             patch.object(ia_sg_client, "post_alert", return_value={"ok": True, "ts": "2.2"}) as mock_sg:
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 200
        assert resp.json()["status"] == "PARTIAL_SUCCESS"
        mock_bq.assert_called_once()
        mock_sg.assert_called_once()
        sg_kwargs = mock_sg.call_args.kwargs
        assert sg_kwargs["formatted_message"] == ""
        assert "AI analysis is currently unavailable" in sg_kwargs["fallback_text"]
        row = mock_bq.call_args.args[0]
        assert row["terminal_status"] == "PARTIAL_SUCCESS"
        assert row["slack_message_ts"] == "2.2"

    def test_bigquery_failure_returns_500_after_slack_checkpoint(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt", return_value=True), \
             patch.object(ia_firestore, "update_receipt") as mock_update_receipt, \
             patch.object(ia_firestore, "create_session"), \
             patch.object(ia_vertex, "normalize_log", return_value=_NORMALIZED), \
             patch.object(ia_vertex, "classify_incident", return_value=_CLASSIFICATION), \
             patch.object(ia_vertex, "format_slack_alert", return_value=_FORMATTED_ALERT), \
             patch.object(ia_bq, "incident_exists_by_idempotency_key", return_value=False), \
             patch.object(ia_bq, "insert_incident", side_effect=RuntimeError("BQ insert error")), \
             patch.object(ia_sg_client, "post_alert", return_value={"ok": True, "ts": "3.3"}) as mock_sg:
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 500
        mock_sg.assert_called_once()
        updates = [call.args[1] for call in mock_update_receipt.call_args_list]
        assert any(update.get("slack_handoff_succeeded") is True for update in updates)
        assert not any(update == {"bigquery_persisted": True} for update in updates)

    def test_slack_gateway_failure_returns_500_without_bigquery_write(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt", return_value=True), \
             patch.object(ia_firestore, "update_receipt"), \
             patch.object(ia_firestore, "create_session"), \
             patch.object(ia_vertex, "normalize_log", return_value=_NORMALIZED), \
             patch.object(ia_vertex, "classify_incident", return_value=_CLASSIFICATION), \
             patch.object(ia_vertex, "format_slack_alert", return_value=_FORMATTED_ALERT), \
             patch.object(ia_bq, "incident_exists_by_idempotency_key") as mock_bq_exists, \
             patch.object(ia_bq, "insert_incident") as mock_bq_insert, \
             patch.object(ia_sg_client, "post_alert", side_effect=RuntimeError("Gateway unreachable")):
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 500
        mock_bq_exists.assert_not_called()
        mock_bq_insert.assert_not_called()
