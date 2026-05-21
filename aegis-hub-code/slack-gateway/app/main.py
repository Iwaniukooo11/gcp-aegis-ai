"""Slack Gateway — FastAPI application entry point."""
import logging

from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.internal_alerts import router as alerts_router
from app.routes.slack_commands import router as commands_router
from app.routes.slack_events import router as events_router

logging.basicConfig(
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s"}',
)

app = FastAPI(title="Aegis Slack Gateway", version="1.0.0")

app.include_router(health_router)
app.include_router(events_router)
app.include_router(commands_router)
app.include_router(alerts_router)
