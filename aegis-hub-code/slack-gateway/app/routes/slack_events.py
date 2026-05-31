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

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.integrations import query_processor_client, slack_web_api
from app.integrations.query_processor_client import QueryProcessorError
from app.security import verify_slack_signature
from app.slack_event_dedup import is_duplicate_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack")

INCIDENT_ID_RE = re.compile(r"INC-\d{4}-\d{6}")
BOT_MENTION_RE = re.compile(r"<@[A-Z0-9]+>")
SESSION_RETRY_ATTEMPTS = 6
SESSION_RETRY_DELAY_S = 5.0


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


def _is_session_not_ready(exc: Exception) -> bool:
    return isinstance(exc, QueryProcessorError) and (
        exc.status_code == 404 or "SESSION_NOT_FOUND" in exc.detail
    )


async def _query_incident_with_session_retry(incident_id: str, question: str) -> dict:
    last_exc: Exception | None = None
    for attempt in range(SESSION_RETRY_ATTEMPTS):
        try:
            return query_processor_client.query_incident(incident_id, question)
        except Exception as exc:
            if not _is_session_not_ready(exc):
                raise
            last_exc = exc
            if attempt + 1 < SESSION_RETRY_ATTEMPTS:
                logger.info(
                    "QP session not ready for %s (%s/%s), retry in %ss",
                    incident_id,
                    attempt + 1,
                    SESSION_RETRY_ATTEMPTS,
                    SESSION_RETRY_DELAY_S,
                )
                await asyncio.sleep(SESSION_RETRY_DELAY_S)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("session retry loop exited without result")


def _slack_text_for_query_error(incident_id: str, exc: Exception) -> str:
    if _is_session_not_ready(exc):
        return (
            f"I do not have session context for *{incident_id}* yet. "
            "Check the incident ID or wait a few seconds after the alert."
        )
    if isinstance(exc, QueryProcessorError) and exc.status_code in (502, 503, 504):
        return (
            f"Query Processor is still warming up for *{incident_id}*. "
            "Wait a moment before asking again."
        )
    if isinstance(exc, httpx.TimeoutException):
        return (
            f"Analysis for *{incident_id}* is taking longer than expected. "
            "Check again in a minute."
        )
    return (
        f"Sorry, I could not analyze incident *{incident_id}* right now. "
        "Please try again shortly."
    )


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
            text=(
                "Could not find an incident ID in your message. "
                "Use format: `@Aegis INC-YYYY-NNNNNN your question`."
            ),
            thread_ts=thread_ts,
        )
        return

    if not question.strip():
        slack_web_api.post_message(
            channel=channel,
            text=(
                f"Please include a question after *{incident_id}* "
                f"(example: `@Aegis {incident_id} what caused this error?`)."
            ),
            thread_ts=thread_ts,
        )
        return

    try:
        result = await _query_incident_with_session_retry(incident_id, question)
        slack_text = result.get("slack_text", "Analysis complete but no response text returned.")
    except Exception as exc:
        logger.error("QP query failed for %s: %s", incident_id, exc)
        slack_text = _slack_text_for_query_error(incident_id, exc)

    try:
        slack_web_api.post_message(channel=channel, text=slack_text, thread_ts=thread_ts)
    except Exception as exc:
        logger.error("Failed to post Slack reply for %s: %s", incident_id, exc)


@router.post("/events", dependencies=[Depends(verify_slack_signature)])
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
