"""Incident Analyzer test fixtures."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TESTS_DIR = str(Path(__file__).parents[1])
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from helpers import load_service_app  # noqa: E402

_IA_ENV = {
    "GCP_PROJECT": "test-project",
    "GCP_REGION": "europe-central2",
    "BIGQUERY_DATASET": "aegis_incidents",
    "BIGQUERY_INCIDENTS_TABLE": "incidents",
    "FIRESTORE_DATABASE": "(default)",
    "SLACK_GATEWAY_URL": "http://sg-test:8080",
    "SLACK_ALERT_CHANNEL_ID": "C_TEST_ALERTS",
    "VERTEX_MODEL": "gemini-1.5-flash",
    "SESSION_TTL_HOURS": "24",
    "RECEIPT_TTL_HOURS": "24",
    "ENVIRONMENT": "dev",
}

_ia_app, _ia_modules = load_service_app("incident-analyzer", _IA_ENV)


@pytest.fixture(scope="session")
def ia_app():
    return _ia_app


@pytest.fixture
def client(ia_app):
    """HTTP test client for the Incident Analyzer app."""
    return TestClient(ia_app, raise_server_exceptions=False)


@pytest.fixture
def ia_bq():
    """Reference to IA bigquery_incidents module for patch.object calls."""
    return _ia_modules["app.integrations.bigquery_incidents"]


@pytest.fixture
def ia_firestore():
    """Reference to IA firestore_sessions module for patch.object calls."""
    return _ia_modules["app.integrations.firestore_sessions"]


@pytest.fixture
def ia_vertex():
    """Reference to IA vertex module for patch.object calls."""
    return _ia_modules["app.integrations.vertex"]


@pytest.fixture
def ia_sg_client():
    """Reference to IA slack_gateway_client module for patch.object calls."""
    return _ia_modules["app.integrations.slack_gateway_client"]
