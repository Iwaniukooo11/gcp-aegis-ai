"""Query Processor test fixtures."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TESTS_DIR = str(Path(__file__).parents[1])
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from helpers import load_service_app  # noqa: E402

_QP_ENV = {
    "GCP_PROJECT": "test-project",
    "GCP_REGION": "europe-central2",
    "BIGQUERY_DATASET": "aegis_incidents",
    "BIGQUERY_INCIDENTS_TABLE": "incidents",
    "FIRESTORE_DATABASE": "(default)",
    "VERTEX_MODEL": "gemini-1.5-flash",
    "ALLOWED_CLIENT_PROJECT_IDS": "mock-client-dev",
    "SESSION_TTL_HOURS": "24",
    "ENVIRONMENT": "dev",
}

_qp_app, _qp_modules = load_service_app("query-processor", _QP_ENV)


@pytest.fixture(scope="session")
def qp_app():
    return _qp_app


@pytest.fixture
def client(qp_app):
    """HTTP test client for the Query Processor app."""
    return TestClient(qp_app, raise_server_exceptions=False)


@pytest.fixture
def qp_bq():
    """Reference to QP bigquery_incidents module for patch.object calls."""
    return _qp_modules["app.integrations.bigquery_incidents"]


@pytest.fixture
def qp_firestore():
    """Reference to QP firestore_sessions module for patch.object calls."""
    return _qp_modules["app.integrations.firestore_sessions"]


@pytest.fixture
def qp_vertex():
    """Reference to QP vertex module for patch.object calls."""
    return _qp_modules["app.integrations.vertex"]


@pytest.fixture
def qp_monitoring():
    """Reference to QP monitoring module for patch.object calls."""
    return _qp_modules["app.integrations.monitoring"]
