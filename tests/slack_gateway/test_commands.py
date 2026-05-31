"""E2E tests for POST /slack/commands — /aegis-latest-incidents slash command.

Paths covered:
  - Happy path: incidents returned and formatted for Slack
  - Custom limit parsed from text
  - Invalid limit text falls back to default (10)
  - Empty incident list produces a "no incidents" message
  - Query Processor failure posts error via response_url
  - Unknown command name returns ephemeral error
"""
from unittest.mock import patch


def _cmd_payload(text: str = "", response_url: str = "http://test-response-url") -> dict:
    return {
        "command": "/aegis-latest-incidents",
        "text": text,
        "response_url": response_url,
        "user_id": "U_ENGINEER",
        "channel_id": "C_TEST",
    }


def _post_cmd(client, signed_slack_form, text: str = "", response_url: str = "http://test-response-url") -> object:
    return client.post(
        "/slack/commands",
        **signed_slack_form(_cmd_payload(text=text, response_url=response_url)),
    )


class TestLatestIncidentsCommand:
    def test_acks_immediately_with_ephemeral_message(self, client, sg_qp_client, sg_slack_web_api, signed_slack_form):
        with patch.object(sg_qp_client, "get_latest_incidents", return_value={"incidents": [], "count": 0}), \
             patch.object(sg_slack_web_api, "post_to_response_url"):
            resp = _post_cmd(client, signed_slack_form)

        assert resp.status_code == 200
        body = resp.json()
        assert body["response_type"] == "ephemeral"
        assert "10" in body["text"]

    def test_happy_path_formats_and_posts_incident_list(
        self, client, sg_qp_client, sg_slack_web_api, sample_bq_rows, signed_slack_form
    ):
        qp_result = {
            "incidents": [{**row, "minutes_ago": 5} for row in sample_bq_rows],
            "count": 2,
            "limit": 10,
        }
        with patch.object(sg_qp_client, "get_latest_incidents", return_value=qp_result) as mock_qp, \
             patch.object(sg_slack_web_api, "post_to_response_url") as mock_post_url:
            resp = _post_cmd(client, signed_slack_form)

        assert resp.status_code == 200
        mock_qp.assert_called_once_with(limit=10)
        mock_post_url.assert_called_once()
        posted_text: str = mock_post_url.call_args.args[1]
        assert "INC-2026-000042" in posted_text
        assert "java-api" in posted_text
        assert "5m ago" in posted_text

    def test_request_completed_short_message_falls_back_to_error_type(
        self, client, sg_qp_client, sg_slack_web_api, sample_bq_rows, signed_slack_form
    ):
        qp_result = {
            "incidents": [
                {
                    **sample_bq_rows[0],
                    "short_message": "Request completed",
                    "error_type": "OutOfMemoryError",
                    "minutes_ago": 5,
                }
            ],
            "count": 1,
            "limit": 10,
        }
        with patch.object(sg_qp_client, "get_latest_incidents", return_value=qp_result), \
             patch.object(sg_slack_web_api, "post_to_response_url") as mock_post_url:
            _post_cmd(client, signed_slack_form)

        posted_text: str = mock_post_url.call_args.args[1]
        assert "OutOfMemoryError" in posted_text
        assert "Request completed" not in posted_text

    def test_response_url_failure_posts_channel_fallback(
        self, client, sg_qp_client, sg_slack_web_api, sample_bq_rows, signed_slack_form
    ):
        qp_result = {
            "incidents": [{**sample_bq_rows[0], "minutes_ago": 5}],
            "count": 1,
            "limit": 10,
        }
        with patch.object(sg_qp_client, "get_latest_incidents", return_value=qp_result), \
             patch.object(sg_slack_web_api, "post_to_response_url", side_effect=RuntimeError("expired")), \
             patch.object(sg_slack_web_api, "post_message", return_value={"ok": True}) as mock_post:
            _post_cmd(client, signed_slack_form)

        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["channel"] == "C_TEST"
        assert "INC-2026-000042" in mock_post.call_args.kwargs["text"]

    def test_custom_limit_passed_to_qp(self, client, sg_qp_client, sg_slack_web_api, signed_slack_form):
        with patch.object(sg_qp_client, "get_latest_incidents", return_value={"incidents": [], "count": 0}) as mock_qp, \
             patch.object(sg_slack_web_api, "post_to_response_url"):
            _post_cmd(client, signed_slack_form, text="5")

        mock_qp.assert_called_once_with(limit=5)

    def test_non_numeric_limit_text_defaults_to_10(self, client, sg_qp_client, sg_slack_web_api, signed_slack_form):
        with patch.object(sg_qp_client, "get_latest_incidents", return_value={"incidents": [], "count": 0}) as mock_qp, \
             patch.object(sg_slack_web_api, "post_to_response_url"):
            _post_cmd(client, signed_slack_form, text="not-a-number")

        mock_qp.assert_called_once_with(limit=10)

    def test_empty_list_posts_no_incidents_message(self, client, sg_qp_client, sg_slack_web_api, signed_slack_form):
        with patch.object(sg_qp_client, "get_latest_incidents", return_value={"incidents": [], "count": 0}), \
             patch.object(sg_slack_web_api, "post_to_response_url") as mock_post_url:
            _post_cmd(client, signed_slack_form)

        posted_text: str = mock_post_url.call_args.args[1]
        assert "No recent incidents" in posted_text

    def test_qp_failure_posts_error_via_response_url(self, client, sg_qp_client, sg_slack_web_api, signed_slack_form):
        with patch.object(sg_qp_client, "get_latest_incidents", side_effect=RuntimeError("BQ down")), \
             patch.object(sg_slack_web_api, "post_to_response_url") as mock_post_url:
            resp = _post_cmd(client, signed_slack_form)

        assert resp.status_code == 200
        mock_post_url.assert_called_once()
        posted_text: str = mock_post_url.call_args.args[1]
        assert "failed" in posted_text.lower() or "Failed" in posted_text

    def test_unknown_command_returns_ephemeral_error(self, client, signed_slack_form):
        resp = client.post(
            "/slack/commands",
            **signed_slack_form({"command": "/unknown-cmd", "text": "", "response_url": "http://x"}),
        )
        assert resp.status_code == 200
        assert "Unknown command" in resp.json()["text"]

    def test_unsigned_command_rejected(self, client):
        resp = client.post("/slack/commands", data=_cmd_payload())
        assert resp.status_code == 401
