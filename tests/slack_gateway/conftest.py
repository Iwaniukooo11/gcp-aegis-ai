"""Slack Gateway test fixtures.

Module-level code loads the SG FastAPI app in isolation and captures
module references for patching.  All fixtures in this file are scoped to
tests inside the slack_gateway/ package only.
"""
import sys
import hmac
import json
import time
from pathlib import Path
from hashlib import sha256
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

_TESTS_DIR = str(Path(__file__).parents[1])
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from helpers import load_service_app  # noqa: E402

_SG_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "SLACK_SIGNING_SECRET": "test-signing-secret",
    "QUERY_PROCESSOR_URL": "http://qp-test:8080",
    "DEFAULT_SLACK_CHANNEL_ID": "C_TEST_CHANNEL",
    "INTERNAL_ALERT_ALLOWED_SERVICE_ACCOUNT": "aegis-incident-analyzer-sa@aegis-hub-2137.iam.gserviceaccount.com",
    "ENVIRONMENT": "dev",
}

_sg_app, _sg_modules = load_service_app("slack-gateway", _SG_ENV)


@pytest.fixture(scope="session")
def sg_app():
    return _sg_app


@pytest.fixture
def client(sg_app):
    """HTTP test client for the Slack Gateway app."""
    return TestClient(sg_app, raise_server_exceptions=False)


@pytest.fixture
def sg_slack_web_api():
    """Reference to the SG slack_web_api module for patch.object calls."""
    return _sg_modules["app.integrations.slack_web_api"]


@pytest.fixture
def sg_qp_client():
    """Reference to the SG query_processor_client module for patch.object calls."""
    return _sg_modules["app.integrations.query_processor_client"]


@pytest.fixture
def sg_security():
    """Reference to the SG security module for patch.object calls."""
    return _sg_modules["app.security"]


def _slack_headers(body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    base = b"v0:" + timestamp.encode() + b":" + body
    signature = "v0=" + hmac.new(_SG_ENV["SLACK_SIGNING_SECRET"].encode(), base, sha256).hexdigest()
    return {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
    }


@pytest.fixture
def signed_slack_json():
    """Return kwargs for TestClient requests with a signed Slack JSON body."""
    def _build(payload: dict) -> dict:
        body = json.dumps(payload, separators=(",", ":")).encode()
        return {
            "content": body,
            "headers": {
                **_slack_headers(body),
                "Content-Type": "application/json",
            },
        }

    return _build


@pytest.fixture
def signed_slack_form():
    """Return kwargs for TestClient requests with a signed Slack form body."""
    def _build(payload: dict) -> dict:
        body = urlencode(payload).encode()
        return {
            "content": body,
            "headers": {
                **_slack_headers(body),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        }

    return _build
