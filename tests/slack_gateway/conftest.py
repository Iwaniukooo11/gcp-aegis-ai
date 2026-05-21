"""Slack Gateway test fixtures.

Module-level code loads the SG FastAPI app in isolation and captures
module references for patching.  All fixtures in this file are scoped to
tests inside the slack_gateway/ package only.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TESTS_DIR = str(Path(__file__).parents[1])
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from helpers import load_service_app  # noqa: E402

_SG_ENV = {
    "SLACK_BOT_TOKEN": "xoxb-test-token",
    "QUERY_PROCESSOR_URL": "http://qp-test:8080",
    "DEFAULT_SLACK_CHANNEL_ID": "C_TEST_CHANNEL",
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
