"""Worker entrypoint.

Run with:  ``dramatiq worker.main``
"""

from __future__ import annotations

import dramatiq

from app.infrastructure.logging import configure_logging, get_logger
from app.settings import get_settings
from worker.broker import configure_broker

settings = get_settings()
configure_logging(level=settings.log_level, json_output=not settings.is_local)
logger = get_logger("worker")

configure_broker(settings.redis_url, settings.queue_namespace)

import worker.tasks  # noqa: E402, F401 (imported to register dramatiq actors)


@dramatiq.actor(max_retries=0, queue_name="health")
def heartbeat(token: str) -> str:
    """Round-trips a token through the queue.

    Used by the container health check and by the Phase 1 integration test to
    prove the broker, the worker process and the actor registry all work.
    """
    logger.info("heartbeat", token=token)
    return token
