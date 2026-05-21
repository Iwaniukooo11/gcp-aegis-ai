import asyncio
import logging
import os

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


async def _chaos_auto_loop(settings: Settings) -> None:
    port = os.environ.get("PORT", "8000")
    base_url = f"http://127.0.0.1:{port}"
    await asyncio.sleep(settings.chaos_auto_initial_delay_seconds)
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        while True:
            if settings.chaos_enabled:
                try:
                    await client.post("/chaos/exception?type=value_error")
                    logger.info("chaos auto triggered PYTHON_EXCEPTION_VALUE_ERROR")
                except httpx.HTTPError as exc:
                    logger.debug("chaos auto exception trigger completed with %s", exc.__class__.__name__)
            await asyncio.sleep(settings.chaos_auto_interval_seconds)


def start_chaos_auto_task(settings: Settings) -> asyncio.Task[None] | None:
    if not settings.chaos_auto_mode or not settings.chaos_enabled:
        return None
    return asyncio.create_task(_chaos_auto_loop(settings))
