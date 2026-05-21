import json

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import error_response
from app.java_client import (
    DownstreamBadResponseError,
    DownstreamTimeoutError,
    JavaApiClient,
    JavaPricingResponse,
)
from app.main import create_app


class FakeJavaClient:
    def __init__(
        self,
        *,
        pricing: JavaPricingResponse | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.pricing = pricing or JavaPricingResponse(
            service_name="java-api",
            client_project_id="aegis-client-420",
            environment="local",
            scenario="JAVA_PRICING",
            currency="USD",
            subtotal_cents=1299,
            tax_cents=104,
            total_cents=1403,
        )
        self.exception = exception
        self.correlation_ids: list[str] = []

    async def get_pricing(self, correlation_id: str) -> JavaPricingResponse:
        self.correlation_ids.append(correlation_id)
        if self.exception:
            raise self.exception
        return self.pricing


def make_client(settings: Settings | None = None, java_client=None) -> TestClient:
    app = create_app(settings or Settings())
    if java_client is not None:
        app.state.java_client = java_client
    return TestClient(app)


def test_liveness_returns_default_metadata() -> None:
    client = make_client()

    response = client.get("/healthz/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "live",
        "service_name": "python-api",
        "environment": "local",
        "client_project_id": "aegis-client-420",
    }
    assert response.headers["X-Correlation-ID"]


def test_readiness_returns_default_metadata() -> None:
    client = make_client()

    response = client.get("/healthz/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service_name": "python-api",
        "environment": "local",
        "client_project_id": "aegis-client-420",
    }


def test_info_returns_service_metadata() -> None:
    client = make_client()

    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "python-api",
        "client_project_id": "aegis-client-420",
        "environment": "local",
        "team": "demo",
        "version": "0.1.0",
    }


def test_work_returns_deterministic_workload_response() -> None:
    client = make_client()

    response = client.get("/api/work")

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "python-api",
        "client_project_id": "aegis-client-420",
        "environment": "local",
        "scenario": "PYTHON_WORK",
        "work_units": 17,
        "result": "completed",
    }


def test_checkout_calls_java_pricing_and_returns_checkout() -> None:
    java_client = FakeJavaClient()
    client = make_client(java_client=java_client)

    response = client.get("/api/checkout", headers={"X-Correlation-ID": "checkout-test-001"})

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "python-api",
        "client_project_id": "aegis-client-420",
        "environment": "local",
        "scenario": "PYTHON_CHECKOUT",
        "upstream_service": "java-api",
        "currency": "USD",
        "subtotal_cents": 1299,
        "tax_cents": 104,
        "total_cents": 1403,
        "checkout_id": "checkout-local-001",
        "result": "completed",
    }
    assert java_client.correlation_ids == ["checkout-test-001"]


def test_correlation_id_is_propagated() -> None:
    client = make_client()

    response = client.get("/api/info", headers={"X-Correlation-ID": "local-test-001"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "local-test-001"


def test_correlation_id_is_generated_when_missing() -> None:
    client = make_client()

    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"]


def test_settings_can_be_overridden() -> None:
    client = make_client(
        Settings(
            SERVICE_NAME="python-api-test",
            CLIENT_PROJECT_ID="test-project",
            ENVIRONMENT="test",
            TEAM="platform",
            VERSION="9.9.9",
        )
    )

    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "python-api-test",
        "client_project_id": "test-project",
        "environment": "test",
        "team": "platform",
        "version": "9.9.9",
    }


def test_settings_read_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("CLIENT_PROJECT_ID", "env-project")
    monkeypatch.setenv("ENVIRONMENT", "env")
    monkeypatch.setenv("TEAM", "observability")

    client = make_client(Settings())

    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "python-api",
        "client_project_id": "env-project",
        "environment": "env",
        "team": "observability",
        "version": "0.1.0",
    }


def test_error_response_shape() -> None:
    response = error_response(
        status_code=504,
        code="DOWNSTREAM_TIMEOUT",
        message="Timed out while calling java-api",
        service_name="python-api",
        scenario="PYTHON_DOWNSTREAM_TIMEOUT",
        correlation_id="local-test-001",
        error_type="DownstreamTimeoutError",
    )

    assert response.status_code == 504
    assert json.loads(response.body) == {
        "error": {
            "code": "DOWNSTREAM_TIMEOUT",
            "message": "Timed out while calling java-api",
            "service_name": "python-api",
            "scenario": "PYTHON_DOWNSTREAM_TIMEOUT",
            "correlation_id": "local-test-001",
            "error_type": "DownstreamTimeoutError",
        }
    }


def test_request_log_is_single_line_json(capsys) -> None:
    client = make_client()

    response = client.get("/api/info", headers={"X-Correlation-ID": "log-test-001"})

    assert response.status_code == 200
    captured = capsys.readouterr()
    log_line = captured.out.strip().splitlines()[-1]
    payload = json.loads(log_line)
    assert payload["severity"] == "INFO"
    assert payload["message"] == "Request completed"
    assert payload["service_name"] == "python-api"
    assert payload["client_project_id"] == "aegis-client-420"
    assert payload["environment"] == "local"
    assert payload["team"] == "demo"
    assert payload["correlation_id"] == "log-test-001"
    assert payload["http_method"] == "GET"
    assert payload["path"] == "/api/info"
    assert payload["status_code"] == 200
    assert payload["incident_candidate"] is False
    assert isinstance(payload["duration_ms"], float)


def test_checkout_timeout_returns_standard_error_and_log(capsys) -> None:
    client = make_client(java_client=FakeJavaClient(exception=DownstreamTimeoutError("timed out")))

    response = client.get("/api/checkout", headers={"X-Correlation-ID": "timeout-test-001"})

    assert response.status_code == 504
    assert response.headers["X-Correlation-ID"] == "timeout-test-001"
    assert response.json() == {
        "error": {
            "code": "DOWNSTREAM_TIMEOUT",
            "message": "Timed out while calling java-api",
            "service_name": "python-api",
            "scenario": "PYTHON_DOWNSTREAM_TIMEOUT",
            "correlation_id": "timeout-test-001",
            "error_type": "DownstreamTimeoutError",
        }
    }
    payload = latest_request_log(capsys)
    assert payload["severity"] == "ERROR"
    assert payload["incident_candidate"] is True
    assert payload["scenario"] == "PYTHON_DOWNSTREAM_TIMEOUT"
    assert payload["error_type"] == "DownstreamTimeoutError"
    assert payload["correlation_id"] == "timeout-test-001"
    assert payload["upstream_service"] == "java-api"
    assert payload["stack_trace_preview"] == "java-api request exceeded configured timeout"


def test_checkout_downstream_5xx_returns_bad_gateway() -> None:
    client = make_client(java_client=FakeJavaClient(exception=DownstreamBadResponseError("java-api returned 503")))

    response = client.get("/api/checkout", headers={"X-Correlation-ID": "bad-response-test-001"})

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "DOWNSTREAM_BAD_RESPONSE",
            "message": "java-api returned an invalid response",
            "service_name": "python-api",
            "scenario": "PYTHON_DOWNSTREAM_5XX",
            "correlation_id": "bad-response-test-001",
            "error_type": "DownstreamBadResponseError",
        }
    }


def test_python_value_error_chaos_returns_standard_error(capsys) -> None:
    client = make_client()

    response = client.post("/chaos/exception?type=value_error", headers={"X-Correlation-ID": "value-error-001"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "PYTHON_VALUE_ERROR",
            "message": "Python value error chaos exception",
            "service_name": "python-api",
            "scenario": "PYTHON_EXCEPTION_VALUE_ERROR",
            "correlation_id": "value-error-001",
            "error_type": "ValueError",
        }
    }
    payload = latest_request_log(capsys)
    assert payload["severity"] == "ERROR"
    assert payload["scenario"] == "PYTHON_EXCEPTION_VALUE_ERROR"
    assert payload["error_type"] == "ValueError"
    assert payload["incident_candidate"] is True
    preview = payload["stack_trace_preview"]
    assert "Traceback" in preview
    assert "chaos.py" in preview
    assert "ValueError" in preview


def test_python_runtime_error_chaos_returns_standard_error() -> None:
    client = make_client()

    response = client.post("/chaos/exception?type=runtime_error")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PYTHON_RUNTIME_ERROR"
    assert response.json()["error"]["scenario"] == "PYTHON_EXCEPTION_RUNTIME_ERROR"
    assert response.json()["error"]["error_type"] == "RuntimeError"


def test_invalid_python_chaos_type_returns_bad_request() -> None:
    client = make_client()

    response = client.post("/chaos/exception?type=unsupported")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CHAOS_REQUEST"
    assert response.json()["error"]["scenario"] == "PYTHON_EXCEPTION_INVALID_TYPE"
    assert response.json()["error"]["error_type"] == "InvalidChaosRequest"


def test_python_chaos_disabled_returns_forbidden() -> None:
    client = make_client(Settings(CHAOS_ENABLED=False))

    response = client.post("/chaos/exception?type=value_error")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CHAOS_DISABLED"
    assert response.json()["error"]["scenario"] == "PYTHON_CHAOS_DISABLED"


def test_java_client_forwards_correlation_id() -> None:
    seen_headers: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers["X-Correlation-ID"])
        return httpx.Response(
            200,
            json={
                "service_name": "java-api",
                "client_project_id": "aegis-client-420",
                "environment": "local",
                "scenario": "JAVA_PRICING",
                "currency": "USD",
                "subtotal_cents": 1299,
                "tax_cents": 104,
                "total_cents": 1403,
            },
        )

    java_client = JavaApiClient(Settings(JAVA_API_BASE_URL="http://java-api"), transport=httpx.MockTransport(handler))

    pricing = anyio.run(java_client.get_pricing, "forward-test-001")

    assert pricing.total_cents == 1403
    assert seen_headers == ["forward-test-001"]


def test_java_client_maps_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    java_client = JavaApiClient(Settings(JAVA_API_BASE_URL="http://java-api"), transport=httpx.MockTransport(handler))

    with pytest.raises(DownstreamTimeoutError):
        anyio.run(java_client.get_pricing, "timeout-test-001")


def test_java_client_rejects_malformed_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "pricing"})

    java_client = JavaApiClient(Settings(JAVA_API_BASE_URL="http://java-api"), transport=httpx.MockTransport(handler))

    with pytest.raises(DownstreamBadResponseError):
        anyio.run(java_client.get_pricing, "malformed-test-001")


def latest_request_log(capsys) -> dict:
    captured = capsys.readouterr()
    log_line = captured.out.strip().splitlines()[-1]
    return json.loads(log_line)
