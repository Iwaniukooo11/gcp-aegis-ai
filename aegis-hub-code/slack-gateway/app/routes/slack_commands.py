"""Slack slash command handler for /aegis-latest-incidents."""
import logging

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app.integrations import query_processor_client, slack_web_api

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack")


def _format_incident_line(inc: dict) -> str:
    mins = inc.get("minutes_ago")
    age = f"{mins}m ago" if mins is not None else "unknown age"
    short = inc.get("short_message") or ""
    error_type = inc.get("error_type") or ""
    if short.strip() == "Request completed" and error_type:
        short = error_type
    elif not short.strip() and error_type:
        short = error_type
    return (
        f"• *{inc['incident_id']}* — {inc.get('service_name', '?')} "
        f"| {inc.get('severity', '?')} | {age}\n  {short}"
    )


def _format_incidents_list(data: dict) -> str:
    incidents = data.get("incidents", [])
    if not incidents:
        return "No recent incidents found."

    lines = [f"*Recent incidents ({data.get('count', 0)}):*"]
    for inc in incidents:
        lines.append(_format_incident_line(inc))
    return "\n".join(lines)


async def _fetch_and_post(
    limit: int,
    response_url: str,
    channel_id: str,
    user_id: str,
) -> None:
    try:
        data = query_processor_client.get_latest_incidents(limit=limit)
        text = _format_incidents_list(data)
    except Exception as exc:
        logger.error("QP latest incidents failed: %s", exc)
        text = "Failed to fetch incidents. Please try again."

    try:
        slack_web_api.post_to_response_url(response_url, text)
    except Exception as exc:
        logger.warning("response_url post failed: %s — posting to channel", exc)
        if channel_id:
            slack_web_api.post_message(
                channel=channel_id,
                text=f"<@{user_id}> {text}" if user_id else text,
            )


@router.post("/commands")
async def slack_commands(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    form = await request.form()
    command = form.get("command", "")
    response_url = str(form.get("response_url", ""))
    channel_id = str(form.get("channel_id", ""))
    user_id = str(form.get("user_id", ""))

    if command != "/aegis-latest-incidents":
        return JSONResponse({"response_type": "ephemeral", "text": f"Unknown command: {command}"})

    text = str(form.get("text", "")).strip()
    try:
        limit = int(text) if text else 10
        limit = max(1, min(50, limit))
    except ValueError:
        limit = 10

    background_tasks.add_task(_fetch_and_post, limit, response_url, channel_id, user_id)

    return JSONResponse({
        "response_type": "in_channel",
        "text": f"/aegis-latest-incidents — fetching the last {limit} incidents…",
    })
