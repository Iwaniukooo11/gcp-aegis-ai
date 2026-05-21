import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.chaos_auto import start_chaos_auto_task
from app.config import Settings, get_settings
from app.context import correlation_id_var
from app.errors import error_response
from app.logging_config import configure_logging
from app.middleware import CorrelationIdMiddleware
from app.observability import set_observability, stack_trace_preview
from app.routers import chaos, health, info, workload


def _python_exception_response(request: Request, exc: Exception, default_scenario: str):
    settings = request.app.state.settings
    scenario = getattr(request.state, "scenario", default_scenario)
    error_type = exc.__class__.__name__
    code = "PYTHON_VALUE_ERROR" if isinstance(exc, ValueError) else "PYTHON_RUNTIME_ERROR"
    message = "Python value error chaos exception" if isinstance(exc, ValueError) else "Python runtime error chaos exception"
    set_observability(
        request,
        scenario=scenario,
        error_type=error_type,
        stack_trace_preview=stack_trace_preview(exc),
    )
    return error_response(
        status_code=500,
        code=code,
        message=message,
        service_name=settings.service_name,
        scenario=scenario,
        correlation_id=correlation_id_var.get() or "unknown",
        error_type=error_type,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    task = start_chaos_auto_task(app.state.settings)
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings)

    app = FastAPI(title="Aegis Python API", version=app_settings.version, lifespan=_lifespan)
    app.state.settings = app_settings
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)
    app.include_router(info.router)
    app.include_router(workload.router)
    app.include_router(chaos.router)

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError):
        return _python_exception_response(request, exc, "PYTHON_EXCEPTION_VALUE_ERROR")

    @app.exception_handler(RuntimeError)
    async def handle_runtime_error(request: Request, exc: RuntimeError):
        return _python_exception_response(request, exc, "PYTHON_EXCEPTION_RUNTIME_ERROR")

    return app


app = create_app()
