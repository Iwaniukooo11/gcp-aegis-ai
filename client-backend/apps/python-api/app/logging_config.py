import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.context import correlation_id_var


class JsonLogFormatter(logging.Formatter):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "service_name": self._settings.service_name,
            "client_project_id": self._settings.client_project_id,
            "environment": self._settings.environment,
            "team": self._settings.team,
        }

        correlation_id = getattr(record, "correlation_id", None) or correlation_id_var.get()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        for key in (
            "scenario",
            "error_type",
            "incident_candidate",
            "http_method",
            "path",
            "status_code",
            "duration_ms",
            "stack_trace_preview",
            "upstream_service",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        return json.dumps(payload, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter(settings))

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.handlers = []
    uvicorn_error_logger.propagate = True

    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
