"""E2E tests for POST /v1/internal/incidents/alert — Incident Analyzer → Gateway.

Paths covered:
  - Happy path: formatted_message posted to Slack channel
  - Only fallback_text present: fallback_text is posted
  - Both messages empty: 400 Bad Request
  - Slack API failure: 500 returned
"""
from unittest.mock import patch

_ALERT_BASE = {
    "incident_id": "INC-2026-000042",
    "client_project_id": "mock-client-dev",
    "service_name": "java-api",
    "severity": "ERROR",
    "error_type": "OutOfMemoryError",
    "short_message": "Java heap space",
    "sanitized_stack_trace_preview": "java.lang.OutOfMemoryError...",
    "ai_summary": "Heap exhausted by unbounded processing.",
    "ai_recommendation": "Increase JVM heap limits.",
}


class TestReceiveAlert:
    def test_posts_formatted_message_to_default_channel(self, client, sg_slack_web_api, sg_security):
        payload = {**_ALERT_BASE, "formatted_message": "*🚨 INC-2026-000042* — java-api OOM", "fallback_text": "fallback"}
        with patch.object(
            sg_security.id_token,
            "verify_oauth2_token",
            return_value={"email": "aegis-incident-analyzer-sa@aegis-hub-2137.iam.gserviceaccount.com"},
        ), patch.object(sg_slack_web_api, "post_message", return_value={"ok": True, "ts": "1.1"}) as mock_post:
            resp = client.post(
                "/v1/internal/incidents/alert",
                json=payload,
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["incident_id"] == "INC-2026-000042"
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["text"] == "*🚨 INC-2026-000042* — java-api OOM"
        assert mock_post.call_args.kwargs["channel"] == "C_TEST_CHANNEL"

    def test_fallback_text_used_when_formatted_message_empty(self, client, sg_slack_web_api, sg_security):
        payload = {**_ALERT_BASE, "formatted_message": "", "fallback_text": "Fallback: OOM detected in java-api"}
        with patch.object(
            sg_security.id_token,
            "verify_oauth2_token",
            return_value={"email": "aegis-incident-analyzer-sa@aegis-hub-2137.iam.gserviceaccount.com"},
        ), patch.object(sg_slack_web_api, "post_message", return_value={"ok": True, "ts": "2.2"}) as mock_post:
            resp = client.post(
                "/v1/internal/incidents/alert",
                json=payload,
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 200
        assert mock_post.call_args.kwargs["text"] == "Fallback: OOM detected in java-api"

    def test_both_messages_empty_returns_400(self, client, sg_slack_web_api, sg_security):
        payload = {**_ALERT_BASE, "formatted_message": "", "fallback_text": ""}
        with patch.object(
            sg_security.id_token,
            "verify_oauth2_token",
            return_value={"email": "aegis-incident-analyzer-sa@aegis-hub-2137.iam.gserviceaccount.com"},
        ), patch.object(sg_slack_web_api, "post_message") as mock_post:
            resp = client.post(
                "/v1/internal/incidents/alert",
                json=payload,
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 400
        mock_post.assert_not_called()

    def test_slack_api_failure_returns_500(self, client, sg_slack_web_api, sg_security):
        payload = {**_ALERT_BASE, "formatted_message": "alert text", "fallback_text": ""}
        with patch.object(
            sg_security.id_token,
            "verify_oauth2_token",
            return_value={"email": "aegis-incident-analyzer-sa@aegis-hub-2137.iam.gserviceaccount.com"},
        ), patch.object(sg_slack_web_api, "post_message", side_effect=RuntimeError("Slack API down")):
            resp = client.post(
                "/v1/internal/incidents/alert",
                json=payload,
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 500

    def test_missing_bearer_token_rejected_before_slack_post(self, client, sg_slack_web_api):
        payload = {**_ALERT_BASE, "formatted_message": "alert text", "fallback_text": ""}
        with patch.object(sg_slack_web_api, "post_message") as mock_post:
            resp = client.post("/v1/internal/incidents/alert", json=payload)

        assert resp.status_code == 401
        mock_post.assert_not_called()

    def test_wrong_service_account_rejected(self, client, sg_slack_web_api, sg_security):
        payload = {**_ALERT_BASE, "formatted_message": "alert text", "fallback_text": ""}
        with patch.object(
            sg_security.id_token,
            "verify_oauth2_token",
            return_value={"email": "other-sa@aegis-hub-2137.iam.gserviceaccount.com"},
        ), patch.object(sg_slack_web_api, "post_message") as mock_post:
            resp = client.post(
                "/v1/internal/incidents/alert",
                json=payload,
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 403
        mock_post.assert_not_called()
