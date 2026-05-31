"""Authentication helpers for public Slack routes and internal Hub calls."""

import hmac
import time
from hashlib import sha256

from fastapi import Header, HTTPException, Request, status
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from app.config import get_settings

SLACK_SIGNATURE_VERSION = "v0"
SLACK_MAX_CLOCK_SKEW_SECONDS = 60 * 5


def _external_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    proto = (forwarded_proto or request.url.scheme).split(",")[0].strip()
    host = (forwarded_host or request.headers.get("host") or request.url.netloc).split(",")[0].strip()
    return f"{proto}://{host}"


async def verify_slack_signature(
    request: Request,
    x_slack_request_timestamp: str | None = Header(default=None),
    x_slack_signature: str | None = Header(default=None),
) -> None:
    """Verify Slack's HMAC signature for Events API and slash commands."""
    if not x_slack_request_timestamp or not x_slack_signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_slack_signature")

    try:
        request_ts = int(x_slack_request_timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_slack_timestamp") from exc

    if abs(int(time.time()) - request_ts) > SLACK_MAX_CLOCK_SKEW_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="stale_slack_request")

    body = await request.body()
    base = f"{SLACK_SIGNATURE_VERSION}:{request_ts}:".encode() + body
    expected = (
        SLACK_SIGNATURE_VERSION
        + "="
        + hmac.new(get_settings().slack_signing_secret.encode(), base, sha256).hexdigest()
    )
    if not hmac.compare_digest(expected, x_slack_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_slack_signature")


def verify_internal_alert_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Verify Google ID token for Incident Analyzer alert handoff."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")

    s = get_settings()
    token = authorization.removeprefix("Bearer ").strip()
    audience = _external_base_url(request)
    try:
        claims = id_token.verify_oauth2_token(token, GoogleAuthRequest(), audience=audience)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_bearer_token") from exc

    caller = str(claims.get("email") or "")
    if caller != s.internal_alert_allowed_service_account:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden_internal_caller")
