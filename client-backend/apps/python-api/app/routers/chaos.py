from fastapi import APIRouter, Request

from app.config import Settings
from app.context import correlation_id_var
from app.errors import error_response
from app.observability import set_observability


router = APIRouter(prefix="/chaos", tags=["chaos"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.post("/exception")
def exception(request: Request, type: str):
    settings = _settings(request)
    correlation_id = correlation_id_var.get() or "unknown"

    if not settings.chaos_enabled:
        scenario = "PYTHON_CHAOS_DISABLED"
        error_type = "ChaosDisabled"
        set_observability(request, scenario=scenario, error_type=error_type)
        return error_response(
            status_code=403,
            code="CHAOS_DISABLED",
            message="Chaos endpoints are disabled",
            service_name=settings.service_name,
            scenario=scenario,
            correlation_id=correlation_id,
            error_type=error_type,
        )

    if type == "value_error":
        set_observability(
            request,
            scenario="PYTHON_EXCEPTION_VALUE_ERROR",
            error_type=ValueError.__name__,
            stack_trace_preview="intentional value error chaos exception",
        )
        raise ValueError("intentional value error chaos exception")
    if type == "runtime_error":
        set_observability(
            request,
            scenario="PYTHON_EXCEPTION_RUNTIME_ERROR",
            error_type=RuntimeError.__name__,
            stack_trace_preview="intentional runtime error chaos exception",
        )
        raise RuntimeError("intentional runtime error chaos exception")

    scenario = "PYTHON_EXCEPTION_INVALID_TYPE"
    error_type = "InvalidChaosRequest"
    set_observability(request, scenario=scenario, error_type=error_type)
    return error_response(
        status_code=400,
        code="INVALID_CHAOS_REQUEST",
        message=f"Unsupported Python exception chaos type: {type}",
        service_name=settings.service_name,
        scenario=scenario,
        correlation_id=correlation_id,
        error_type=error_type,
    )
