from fastapi import APIRouter, Request

from app.config import Settings
from app.schemas import InfoResponse


router = APIRouter(prefix="/api", tags=["info"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/info", response_model=InfoResponse)
def info(request: Request) -> InfoResponse:
    settings = _settings(request)
    return InfoResponse(
        service_name=settings.service_name,
        client_project_id=settings.client_project_id,
        environment=settings.environment,
        team=settings.team,
        version=settings.version,
    )
