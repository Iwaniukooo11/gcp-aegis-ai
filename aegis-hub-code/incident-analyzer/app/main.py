"""Incident Analyzer — FastAPI application entry point."""
import logging

from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.pubsub import router as pubsub_router

logging.basicConfig(
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s"}',
)

app = FastAPI(title="Aegis Incident Analyzer", version="1.0.0")

app.include_router(health_router)
app.include_router(pubsub_router)
