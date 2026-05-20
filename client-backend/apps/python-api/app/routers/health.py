from fastapi import APIRouter, Request

from app.config import Settings
from app.schemas import HealthResponse


router = APIRouter(prefix="/healthz", tags=["health"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/live", response_model=HealthResponse)
def live(request: Request) -> HealthResponse:
    settings = _settings(request)
    return HealthResponse(
        status="live",
        service_name=settings.service_name,
        environment=settings.environment,
        client_project_id=settings.client_project_id,
    )


@router.get("/ready", response_model=HealthResponse)
def ready(request: Request) -> HealthResponse:
    settings = _settings(request)
    return HealthResponse(
        status="ready",
        service_name=settings.service_name,
        environment=settings.environment,
        client_project_id=settings.client_project_id,
    )
