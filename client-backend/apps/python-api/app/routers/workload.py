from fastapi import APIRouter, Request

from app.config import Settings
from app.context import correlation_id_var
from app.errors import error_response
from app.java_client import DownstreamBadResponseError, DownstreamTimeoutError, JavaApiClient
from app.observability import set_observability
from app.schemas import CheckoutResponse, WorkResponse


router = APIRouter(prefix="/api", tags=["workload"])
UPSTREAM_SERVICE = "java-api"


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _java_client(request: Request) -> JavaApiClient:
    override = getattr(request.app.state, "java_client", None)
    if override is not None:
        return override
    return JavaApiClient(_settings(request))


def _checkout_failure_message(reason: str) -> str:
    return f"Checkout failed because {reason}"


@router.get("/work", response_model=WorkResponse)
def work(request: Request) -> WorkResponse:
    settings = _settings(request)
    set_observability(request, scenario="PYTHON_WORK")
    return WorkResponse(
        service_name=settings.service_name,
        client_project_id=settings.client_project_id,
        environment=settings.environment,
        scenario="PYTHON_WORK",
        work_units=17,
        result="completed",
    )


@router.get("/checkout", response_model=CheckoutResponse)
async def checkout(request: Request) -> CheckoutResponse:
    settings = _settings(request)
    correlation_id = correlation_id_var.get() or "unknown"
    set_observability(request, scenario="PYTHON_CHECKOUT", upstream_service=UPSTREAM_SERVICE)

    try:
        pricing = await _java_client(request).get_pricing(correlation_id)
    except DownstreamTimeoutError as exc:
        scenario = "PYTHON_DOWNSTREAM_TIMEOUT"
        error_type = exc.__class__.__name__
        reason = str(exc).strip() or "java-api pricing request exceeded configured timeout"
        incident_message = _checkout_failure_message(reason)
        set_observability(
            request,
            scenario=scenario,
            error_type=error_type,
            incident_message=incident_message,
            stack_trace_preview=incident_message,
            upstream_service=UPSTREAM_SERVICE,
        )
        return error_response(
            status_code=504,
            code="DOWNSTREAM_TIMEOUT",
            message=incident_message,
            service_name=settings.service_name,
            scenario=scenario,
            correlation_id=correlation_id,
            error_type=error_type,
        )
    except DownstreamBadResponseError as exc:
        scenario = "PYTHON_DOWNSTREAM_5XX"
        error_type = exc.__class__.__name__
        reason = str(exc).strip() or "java-api pricing returned an invalid response"
        incident_message = _checkout_failure_message(reason)
        set_observability(
            request,
            scenario=scenario,
            error_type=error_type,
            incident_message=incident_message,
            stack_trace_preview=incident_message,
            upstream_service=UPSTREAM_SERVICE,
        )
        return error_response(
            status_code=502,
            code="DOWNSTREAM_BAD_RESPONSE",
            message=incident_message,
            service_name=settings.service_name,
            scenario=scenario,
            correlation_id=correlation_id,
            error_type=error_type,
        )

    return CheckoutResponse(
        service_name=settings.service_name,
        client_project_id=settings.client_project_id,
        environment=settings.environment,
        scenario="PYTHON_CHECKOUT",
        upstream_service=UPSTREAM_SERVICE,
        currency=pricing.currency,
        subtotal_cents=pricing.subtotal_cents,
        tax_cents=pricing.tax_cents,
        total_cents=pricing.total_cents,
        checkout_id="checkout-local-001",
        result="completed",
    )
