"""Slack Web API client for posting messages.

Thin wrapper around Slack's chat.postMessage and response_url posting.
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


def post_message(
    channel: str,
    text: str,
    thread_ts: str | None = None,
) -> dict:
    """Post a message to a Slack channel, optionally in a thread.

    Raises on non-2xx or Slack API error (ok=false).
    """
    s = get_settings()
    payload: dict = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    with httpx.Client(timeout=10) as client:
        response = client.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            json=payload,
            headers={
                "Authorization": f"Bearer {s.slack_bot_token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error')}")
        return data


def post_to_response_url(response_url: str, text: str) -> None:
    """Post a delayed response to a Slack slash command response_url."""
    with httpx.Client(timeout=10) as client:
        response = client.post(
            response_url,
            json={"text": text, "response_type": "in_channel"},
        )
        response.raise_for_status()
