"""Slack slash command handler for /aegis-latest-incidents.

Slack requires a response within 3 seconds. This handler acks immediately
with an ephemeral "fetching..." message and posts the full result via
response_url in a background task.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from app.integrations import query_processor_client, slack_web_api
from app.security import verify_slack_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack")


def _format_incidents_list(data: dict) -> str:
    """Format the QP incidents response as a Slack mrkdwn block."""
    incidents = data.get("incidents", [])
    if not incidents:
        return "No recent incidents found."

    lines = [f"*Recent incidents ({data.get('count', 0)}):*"]
    for inc in incidents:
        mins = inc.get("minutes_ago")
        age = f"{mins}m ago" if mins is not None else "unknown age"
        lines.append(
            f"• *{inc['incident_id']}* — {inc.get('service_name', '?')} "
            f"| {inc.get('severity', '?')} | {age}\n  {inc.get('short_message', '')}"
        )
    return "\n".join(lines)


async def _fetch_and_post(limit: int, response_url: str) -> None:
    """Background task: call QP and post result via response_url."""
    try:
        data = query_processor_client.get_latest_incidents(limit=limit)
        text = _format_incidents_list(data)
    except Exception as exc:
        logger.error("QP latest incidents failed: %s", exc)
        text = "Failed to fetch incidents. Please try again."

    slack_web_api.post_to_response_url(response_url, text)


@router.post("/commands", dependencies=[Depends(verify_slack_signature)])
async def slack_commands(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """Handle Slack slash command payloads."""
    form = await request.form()
    command = form.get("command", "")
    response_url = str(form.get("response_url", ""))

    if command != "/aegis-latest-incidents":
        return JSONResponse({"response_type": "ephemeral", "text": f"Unknown command: {command}"})

    text = str(form.get("text", "")).strip()
    try:
        limit = int(text) if text else 10
        limit = max(1, min(50, limit))
    except ValueError:
        limit = 10

    background_tasks.add_task(_fetch_and_post, limit, response_url)

    return JSONResponse({
        "response_type": "ephemeral",
        "text": f"Fetching the last {limit} incidents...",
    })
