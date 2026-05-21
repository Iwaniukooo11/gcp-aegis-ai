from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict:
    """Readiness probe."""
    return {"status": "ready"}
