"""HTTP client for calling Query Processor endpoints with OIDC auth."""
import logging

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.config import get_settings

logger = logging.getLogger(__name__)


def _oidc_token(audience: str) -> str:
    """Fetch a Google OIDC identity token for the given audience."""
    return id_token.fetch_id_token(Request(), audience)


def _headers(audience: str) -> dict:
    return {
        "Authorization": f"Bearer {_oidc_token(audience)}",
        "Content-Type": "application/json",
    }


def get_latest_incidents(limit: int = 10) -> dict:
    """Call QP GET /v1/incidents/latest and return parsed JSON."""
    s = get_settings()
    base = s.query_processor_url.rstrip("/")
    with httpx.Client(timeout=20) as client:
        response = client.get(
            f"{base}/v1/incidents/latest",
            params={"limit": limit},
            headers=_headers(base),
        )
        response.raise_for_status()
        return response.json()


def query_incident(incident_id: str, text: str) -> dict:
    """Call QP POST /v1/incidents/{incident_id}/query and return parsed JSON."""
    s = get_settings()
    base = s.query_processor_url.rstrip("/")
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{base}/v1/incidents/{incident_id}/query",
            json={"text": text},
            headers=_headers(base),
        )
        response.raise_for_status()
        return response.json()
