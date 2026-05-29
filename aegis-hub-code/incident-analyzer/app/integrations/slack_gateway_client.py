"""HTTP client for calling the Slack Gateway alert endpoint.

Incident Analyzer must not post to Slack directly — it sends a structured
payload to Slack Gateway, which decides channel and message formatting.
"""
import logging

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.config import get_settings

logger = logging.getLogger(__name__)

ALERT_PATH = "/v1/internal/incidents/alert"


def _oidc_token(audience: str) -> str:
    """Fetch a Google OIDC identity token for the given audience."""
    return id_token.fetch_id_token(Request(), audience)


def post_alert(
    incident_id: str,
    client_project_id: str,
    service_name: str,
    severity: str,
    error_type: str,
    short_message: str,
    stack_trace_preview: str,
    ai_summary: str,
    ai_recommendation: str,
    formatted_message: str,
    fallback_text: str,
) -> dict:
    """POST the incident alert payload to Slack Gateway.

    Returns the Gateway JSON response on success.
    Raises httpx.HTTPStatusError on non-2xx so callers can decide retry behaviour.
    """
    s = get_settings()
    gateway_url = s.slack_gateway_url.rstrip("/")
    audience = gateway_url
    token = _oidc_token(audience)

    payload = {
        "incident_id": str(incident_id or ""),
        "client_project_id": str(client_project_id or "unknown"),
        "service_name": str(service_name or "unknown"),
        "severity": str(severity or "ERROR"),
        "error_type": str(error_type or ""),
        "short_message": str(short_message or ""),
        "sanitized_stack_trace_preview": str(stack_trace_preview or ""),
        "ai_summary": str(ai_summary or ""),
        "ai_recommendation": str(ai_recommendation or ""),
        "formatted_message": str(formatted_message or ""),
        "fallback_text": str(fallback_text or ""),
    }

    with httpx.Client(timeout=15) as client:
        response = client.post(
            gateway_url + ALERT_PATH,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as exc:
            body_preview = (response.text or "")[:500]
            raise ValueError(
                f"Slack Gateway returned non-JSON (status={response.status_code}): {body_preview!r}"
            ) from exc
