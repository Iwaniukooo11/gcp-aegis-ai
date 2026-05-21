"""E2E tests for POST /pubsub/push — Pub/Sub push subscription handler.

Paths covered:
  - Full success pipeline: Gemini → BigQuery → Firestore → Slack Gateway
  - Duplicate delivery: existing receipt detected, all downstream steps skipped
  - Bad/undecodeable base64 payload: acked with 200 (no DLQ loop)
  - Gemini enrichment failure: PARTIAL_SUCCESS with fallback text posted to SG
  - BigQuery insert failure: 500 returned so Pub/Sub retries
  - Slack Gateway handoff failure: 500 returned so Pub/Sub retries
    (dedup receipt prevents double BigQuery write on retry)
"""
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

_FORMATTED_ALERT = "*\U0001f6a8 INC-TEST* — java-api | ERROR | OutOfMemoryError\nAI: Heap exhausted."


class TestPubSubPush:
    def test_full_success_pipeline_returns_success_status(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt"), \
             patch.object(ia_firestore, "update_receipt"), \
             patch.object(ia_firestore, "create_session"), \
             patch.object(ia_vertex, "normalize_log", return_value=_NORMALIZED), \
             patch.object(ia_vertex, "classify_incident", return_value=_CLASSIFICATION), \
             patch.object(ia_vertex, "format_slack_alert", return_value=_FORMATTED_ALERT), \
             patch.object(ia_bq, "insert_incident"), \
             patch.object(ia_sg_client, "post_alert", return_value={"ok": True, "ts": "1.1"}):
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUCCESS"
        assert body["incident_id"].startswith("INC-")

    def test_duplicate_delivery_skipped(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        """Already-seen message: receipt exists, nothing else runs."""
        existing = {"incident_id": "INC-2026-000042", "bigquery_persisted": True}
        with patch.object(ia_firestore, "get_receipt", return_value=existing), \
             patch.object(ia_vertex, "normalize_log") as mock_vertex, \
             patch.object(ia_bq, "insert_incident") as mock_bq, \
             patch.object(ia_sg_client, "post_alert") as mock_sg:
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"
        mock_vertex.assert_not_called()
        mock_bq.assert_not_called()
        mock_sg.assert_not_called()

    def test_undecodeable_payload_acked_not_crashed(self, client):
        """Corrupt messages must be acked (200) to avoid infinite DLQ loop."""
        bad_envelope = {
            "message": {
                "data": "THIS_IS_NOT_VALID_BASE64_OR_JSON!!!",
                "messageId": "bad-msg-001",
                "publishTime": "2026-05-21T00:00:00Z",
                "attributes": {},
            },
            "subscription": "projects/test/subscriptions/test-sub",
        }
        resp = client.post("/pubsub/push", json=bad_envelope)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ack_bad_payload"

    def test_gemini_failure_results_in_partial_success(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        """Gemini quota/error: fallback text sent, terminal_status=PARTIAL_SUCCESS."""
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt"), \
             patch.object(ia_firestore, "update_receipt"), \
             patch.object(ia_firestore, "create_session"), \
             patch.object(ia_vertex, "normalize_log", side_effect=Exception("Vertex quota exceeded")), \
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

    def test_bigquery_failure_returns_500_for_pubsub_retry(
        self, client, ia_firestore, ia_vertex, ia_bq, sample_pubsub_envelope
    ):
        """BQ insert fails: 500 so Pub/Sub retries the message."""
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt"), \
             patch.object(ia_firestore, "update_receipt"), \
             patch.object(ia_vertex, "normalize_log", return_value=_NORMALIZED), \
             patch.object(ia_vertex, "classify_incident", return_value=_CLASSIFICATION), \
             patch.object(ia_vertex, "format_slack_alert", return_value=_FORMATTED_ALERT), \
             patch.object(ia_bq, "insert_incident", side_effect=RuntimeError("BQ insert error")):
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 500

    def test_slack_gateway_failure_returns_500_for_pubsub_retry(
        self, client, ia_firestore, ia_vertex, ia_bq, ia_sg_client, sample_pubsub_envelope
    ):
        """SG handoff fails after BQ success: 500 for retry.
        Dedup receipt prevents a second BigQuery row on the retry."""
        with patch.object(ia_firestore, "get_receipt", return_value=None), \
             patch.object(ia_firestore, "create_receipt"), \
             patch.object(ia_firestore, "update_receipt"), \
             patch.object(ia_firestore, "create_session"), \
             patch.object(ia_vertex, "normalize_log", return_value=_NORMALIZED), \
             patch.object(ia_vertex, "classify_incident", return_value=_CLASSIFICATION), \
             patch.object(ia_vertex, "format_slack_alert", return_value=_FORMATTED_ALERT), \
             patch.object(ia_bq, "insert_incident"), \
             patch.object(ia_sg_client, "post_alert", side_effect=RuntimeError("Gateway unreachable")):
            resp = client.post("/pubsub/push", json=sample_pubsub_envelope)

        assert resp.status_code == 500
