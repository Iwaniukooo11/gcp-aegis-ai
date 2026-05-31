"""E2E tests for POST /slack/events — Slack Events API handler.

Paths covered:
  - URL verification challenge (Slack app install handshake)
  - App mention with valid INC-YYYY-NNNNNN + question (happy path)
  - App mention without incident ID (error feedback to Slack)
  - App mention when Query Processor fails (fallback error to Slack)
  - App mention inside a thread (thread_ts forwarded)
  - Non-app_mention event type (silently ignored)
  - Unknown top-level event type (silently ignored)
"""
from unittest.mock import patch


def _make_mention_event(text: str, channel: str = "C_TEST", ts: str = "111.111", thread_ts: str | None = None) -> dict:
    event = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "user": "U_ENGINEER",
            "text": text,
            "ts": ts,
            "channel": channel,
        },
    }
    if thread_ts:
        event["event"]["thread_ts"] = thread_ts
    return event


class TestUrlVerification:
    def test_challenge_echoed_back(self, client, signed_slack_json):
        payload = {"type": "url_verification", "challenge": "xyz-challenge"}
        resp = client.post("/slack/events", **signed_slack_json(payload))
        assert resp.status_code == 200
        assert resp.json() == {"challenge": "xyz-challenge"}

    def test_unsigned_challenge_rejected(self, client):
        resp = client.post("/slack/events", json={"type": "url_verification", "challenge": "xyz-challenge"})
        assert resp.status_code == 401


class TestAppMention:
    def test_happy_path_calls_qp_and_posts_to_slack(self, client, sg_qp_client, sg_slack_web_api, signed_slack_json):
        qp_result = {
            "slack_text": "Memory is high because Java heap is exhausted. Recommendation: increase limits.",
            "timestamp": "2026-05-21T00:00:00+00:00",
        }
        with patch.object(sg_qp_client, "query_incident", return_value=qp_result) as mock_qp, \
             patch.object(sg_slack_web_api, "post_message", return_value={"ok": True, "ts": "1.1"}) as mock_post:
            resp = client.post(
                "/slack/events",
                **signed_slack_json(_make_mention_event("<@UBOT> INC-2026-000042 why is memory spiking")),
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock_qp.assert_called_once_with("INC-2026-000042", "why is memory spiking")
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["text"] == qp_result["slack_text"]
        assert mock_post.call_args.kwargs["channel"] == "C_TEST"

    def test_no_incident_id_posts_error_hint(self, client, sg_qp_client, sg_slack_web_api, signed_slack_json):
        with patch.object(sg_qp_client, "query_incident") as mock_qp, \
             patch.object(sg_slack_web_api, "post_message", return_value={"ok": True}) as mock_post:
            resp = client.post(
                "/slack/events",
                **signed_slack_json(_make_mention_event("<@UBOT> what is the current status")),
            )

        assert resp.status_code == 200
        mock_qp.assert_not_called()
        mock_post.assert_called_once()
        posted_text: str = mock_post.call_args.kwargs["text"]
        assert "INC-" in posted_text

    def test_qp_failure_posts_fallback_error_to_slack(self, client, sg_qp_client, sg_slack_web_api, signed_slack_json):
        with patch.object(sg_qp_client, "query_incident", side_effect=RuntimeError("QP unreachable")), \
             patch.object(sg_slack_web_api, "post_message", return_value={"ok": True}) as mock_post:
            resp = client.post(
                "/slack/events",
                **signed_slack_json(_make_mention_event("<@UBOT> INC-2026-000042 help")),
            )

        assert resp.status_code == 200
        mock_post.assert_called_once()
        assert "INC-2026-000042" in mock_post.call_args.kwargs["text"]

    def test_session_not_found_is_retried_before_success(
        self, client, sg_qp_client, sg_slack_events, sg_slack_web_api, signed_slack_json
    ):
        session_error = sg_qp_client.QueryProcessorError(404, "SESSION_NOT_FOUND")
        with patch.object(sg_slack_events, "SESSION_RETRY_DELAY_S", 0), \
             patch.object(
                 sg_qp_client,
                 "query_incident",
                 side_effect=[session_error, {"slack_text": "Session is ready now."}],
             ) as mock_qp, \
             patch.object(sg_slack_web_api, "post_message", return_value={"ok": True}) as mock_post:
            resp = client.post(
                "/slack/events",
                **signed_slack_json(_make_mention_event("<@UBOT> INC-2026-000042 what happened")),
            )

        assert resp.status_code == 200
        assert mock_qp.call_count == 2
        assert mock_post.call_args.kwargs["text"] == "Session is ready now."

    def test_empty_question_posts_usage_hint(self, client, sg_qp_client, sg_slack_web_api, signed_slack_json):
        with patch.object(sg_qp_client, "query_incident") as mock_qp, \
             patch.object(sg_slack_web_api, "post_message", return_value={"ok": True}) as mock_post:
            resp = client.post(
                "/slack/events",
                **signed_slack_json(_make_mention_event("<@UBOT> INC-2026-000042")),
            )

        assert resp.status_code == 200
        mock_qp.assert_not_called()
        assert "Please include a question" in mock_post.call_args.kwargs["text"]

    def test_thread_ts_forwarded_to_slack(self, client, sg_qp_client, sg_slack_web_api, signed_slack_json):
        with patch.object(sg_qp_client, "query_incident", return_value={"slack_text": "All clear."}), \
             patch.object(sg_slack_web_api, "post_message", return_value={"ok": True}) as mock_post:
            resp = client.post(
                "/slack/events",
                **signed_slack_json(_make_mention_event("<@UBOT> INC-2026-000042 status", thread_ts="555.555")),
            )

        assert resp.status_code == 200
        assert mock_post.call_args.kwargs.get("thread_ts") == "555.555"

    def test_non_app_mention_event_ignored(self, client, sg_qp_client, sg_slack_web_api, signed_slack_json):
        with patch.object(sg_qp_client, "query_incident") as mock_qp, \
             patch.object(sg_slack_web_api, "post_message") as mock_post:
            resp = client.post(
                "/slack/events",
                **signed_slack_json({"type": "event_callback", "event": {"type": "message", "text": "hello there"}}),
            )

        assert resp.status_code == 200
        mock_qp.assert_not_called()
        mock_post.assert_not_called()

    def test_unknown_top_level_event_type_ignored(self, client, signed_slack_json):
        resp = client.post("/slack/events", **signed_slack_json({"type": "app_rate_limited"}))
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
