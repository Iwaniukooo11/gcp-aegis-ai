"""Detached background task helpers for Slack Gateway."""
import asyncio
import logging
from collections.abc import Coroutine

logger = logging.getLogger(__name__)

_PENDING_TASKS: set[asyncio.Task[None]] = set()


def schedule(coro: Coroutine[object, object, None], name: str) -> None:
    """Schedule a coroutine without tying Slack webhook latency to its runtime."""
    task = asyncio.create_task(coro, name=name)
    _PENDING_TASKS.add(task)
    task.add_done_callback(_finish_task)


def _finish_task(task: asyncio.Task[None]) -> None:
    _PENDING_TASKS.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning("Background task cancelled: %s", task.get_name())
    except Exception:
        logger.exception("Background task failed: %s", task.get_name())
