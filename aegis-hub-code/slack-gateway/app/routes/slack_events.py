"""Slack Events API handler.

Handles:
  - url_verification challenge (no auth needed)
  - app_mention events: parse INC-... + question text, fire-and-forget call to QP

The handler returns 200 immediately to satisfy Slack's 3s response requirement.
QP analysis and the final Slack reply happen in a background asyncio task.
"""
import asyncio
import logging
import re

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.integrations import query_processor_client, slack_web_api
from app.slack_event_dedup import is_duplicate_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack")

INCIDENT_ID_RE = re.compile(r"INC-\d{4}-\d{6}")
BOT_MENTION_RE = re.compile(r"<@[A-Z0-9]+>")


def _parse_mention(text: str) -> tuple[str | None, str]:
    """Extract (incident_id, cleaned_question) from a mention text string.

    The incident ID may appear anywhere in the text.
    Bot mention tags are stripped before returning the question.
    """
    match = INCIDENT_ID_RE.search(text)
    incident_id = match.group(0) if match else None
    question = BOT_MENTION_RE.sub("", text).strip()
    if incident_id:
        question = question.replace(incident_id, "").strip()
    return incident_id, question


async def _handle_mention(
    incident_id: str | None,
    question: str,
    channel: str,
    thread_ts: str | None,
) -> None:
    """Background task: call Query Processor and post result to Slack."""
    if incident_id is None:
        slack_web_api.post_message(
            channel=channel,
            text="Could not find an incident ID in your message (expected format: `INC-YYYY-NNNNNN`).",
            thread_ts=thread_ts,
        )
        return

    try:
        result = query_processor_client.query_incident(incident_id, question or "What is the status?")
        slack_text = result.get("slack_text", "Analysis complete but no response text returned.")
    except Exception as exc:
        logger.error("QP query failed for %s: %s", incident_id, exc)
        slack_text = f"Sorry, I could not analyze incident *{incident_id}* right now. Please try again shortly."

    slack_web_api.post_message(channel=channel, text=slack_text, thread_ts=thread_ts)


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """Receive Slack Events API payloads."""
    body = await request.json()

    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body["challenge"]})

    if body.get("type") != "event_callback":
        return JSONResponse({"ok": True})

    event = body.get("event", {})
    if event.get("type") != "app_mention":
        return JSONResponse({"ok": True})

    event_id = body.get("event_id")
    if is_duplicate_event(event_id):
        logger.info("Skipping duplicate Slack event_id=%s", event_id)
        return JSONResponse({"ok": True})

    text = event.get("text", "")
    channel = event.get("channel", get_settings().default_slack_channel_id)
    thread_ts = event.get("thread_ts") or event.get("ts")

    incident_id, question = _parse_mention(text)

    background_tasks.add_task(_handle_mention, incident_id, question, channel, thread_ts)

    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)
