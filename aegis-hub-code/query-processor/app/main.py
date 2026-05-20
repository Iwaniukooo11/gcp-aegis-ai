"""Query Processor — FastAPI application entry point."""
import logging

from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.incidents import router as incidents_router

logging.basicConfig(
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s"}',
)

app = FastAPI(title="Aegis Query Processor", version="1.0.0")

app.include_router(health_router)
app.include_router(incidents_router)
