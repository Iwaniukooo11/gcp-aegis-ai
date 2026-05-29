"""Internal alert endpoint — receives incident alerts from Incident Analyzer.

POST /v1/internal/incidents/alert
  Auth: OIDC Bearer token from Incident Analyzer service account
  Posts formatted_message (or fallback_text) to DEFAULT_SLACK_CHANNEL_ID
"""
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from app.config import get_settings
from app.integrations import slack_web_api

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/internal")


class AlertPayload(BaseModel):
    incident_id: str
    client_project_id: str
    service_name: str
    severity: str
    error_type: str = ""
    short_message: str = ""
    sanitized_stack_trace_preview: str = ""
    ai_summary: str = ""
    ai_recommendation: str = ""
    formatted_message: str = ""
    fallback_text: str = ""

    @field_validator(
        "incident_id",
        "client_project_id",
        "service_name",
        "severity",
        "error_type",
        "short_message",
        "sanitized_stack_trace_preview",
        "ai_summary",
        "ai_recommendation",
        "formatted_message",
        "fallback_text",
        mode="before",
    )
    @classmethod
    def coerce_strings(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value)


@router.post("/incidents/alert", status_code=status.HTTP_200_OK)
async def receive_alert(payload: AlertPayload) -> dict:
    """Post an incident alert to the configured Slack channel."""
    message = payload.formatted_message.strip() or payload.fallback_text.strip()
    if not message:
        raise HTTPException(status_code=400, detail="formatted_message and fallback_text are both empty")

    channel = get_settings().default_slack_channel_id
    try:
        result = slack_web_api.post_message(channel=channel, text=message)
    except Exception as exc:
        logger.error("Failed to post Slack alert for %s: %s", payload.incident_id, exc)
        raise HTTPException(status_code=500, detail="slack_post_failed") from exc

    logger.info("Alert posted for %s, ts=%s", payload.incident_id, result.get("ts"))
    return {"ok": True, "ts": result.get("ts"), "incident_id": payload.incident_id}
