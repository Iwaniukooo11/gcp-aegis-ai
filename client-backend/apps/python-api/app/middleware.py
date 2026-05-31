import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.context import correlation_id_var
from app.observability import stack_trace_preview


LOGGER = logging.getLogger("python-api.requests")
CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid4())
        token = correlation_id_var.set(correlation_id)
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            LOGGER.exception(
                "Unhandled request error",
                extra={
                    "correlation_id": correlation_id,
                    "scenario": getattr(request.state, "scenario", "PYTHON_UNHANDLED_EXCEPTION"),
                    "error_type": exc.__class__.__name__,
                    "incident_candidate": True,
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "stack_trace_preview": stack_trace_preview(exc),
                    "upstream_service": getattr(request.state, "upstream_service", None),
                },
            )
            raise
        finally:
            correlation_id_var.reset(token)

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers[CORRELATION_HEADER] = correlation_id
        is_error = response.status_code >= 500
        log_method = LOGGER.error if is_error else LOGGER.info
        error_type = getattr(request.state, "error_type", None)
        incident_message = getattr(request.state, "incident_message", None)
        log_message = (
            incident_message
            if is_error and incident_message
            else f"{error_type}: {request.method} {request.url.path} failed"
            if is_error and error_type
            else (
                f"HTTP {response.status_code}: {request.method} {request.url.path}"
                if is_error
                else "Request completed"
            )
        )
        log_method(
            log_message,
            extra={
                "correlation_id": correlation_id,
                "scenario": getattr(request.state, "scenario", None),
                "error_type": getattr(request.state, "error_type", None),
                "incident_candidate": is_error,
                "http_method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "stack_trace_preview": getattr(request.state, "stack_trace_preview", None),
                "upstream_service": getattr(request.state, "upstream_service", None),
            },
        )
        return response
