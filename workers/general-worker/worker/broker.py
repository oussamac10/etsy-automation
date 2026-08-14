"""Dramatiq broker wiring (ADR-0001).

The broker is built by a factory so tests can substitute a stub broker without
connecting to Redis.
"""

from __future__ import annotations

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import (
    AgeLimit,
    Callbacks,
    CurrentMessage,
    Retries,
    ShutdownNotifications,
    TimeLimit,
)

# Long enough for an image round-trip, short enough that a hung job is noticed.
DEFAULT_TIME_LIMIT_MS = 10 * 60 * 1000
DEFAULT_MAX_AGE_MS = 60 * 60 * 1000


def build_broker(redis_url: str, namespace: str = "etsy_automation") -> RedisBroker:
    # dramatiq ships no type information; the constructor is untyped.
    broker = RedisBroker(
        url=redis_url,
        namespace=namespace,
        middleware=[
            AgeLimit(max_age=DEFAULT_MAX_AGE_MS),
            TimeLimit(time_limit=DEFAULT_TIME_LIMIT_MS),
            ShutdownNotifications(),
            Callbacks(),
            # Actors read the attempt count off the current message to decide whether a
            # retry is still allowed; without this middleware it is not reachable.
            CurrentMessage(),
            # Retry decisions are made by worker.retry.should_retry inside each actor;
            # this bound is the hard ceiling.
            Retries(max_retries=5),
        ],
    )  # type: ignore[no-untyped-call]
    return broker


def configure_broker(redis_url: str | None = None, namespace: str | None = None) -> RedisBroker:
    """Install the global broker. Called once by the worker entrypoint."""
    broker = build_broker(
        redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        namespace or os.environ.get("QUEUE_NAMESPACE", "etsy_automation"),
    )
    dramatiq.set_broker(broker)
    return broker
