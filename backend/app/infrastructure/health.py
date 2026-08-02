"""Dependency health checks used by ``/api/health``.

Each probe is independent, bounded by a timeout, and reports a category rather
than an exception payload — connection strings often contain credentials.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

DEFAULT_TIMEOUT_SECONDS = 3.0


class ComponentStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    status: ComponentStatus
    detail: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True, slots=True)
class HealthReport:
    status: ComponentStatus
    service: str
    version: str
    app_env: str
    checked_at: datetime
    components: dict[str, ComponentHealth] = field(default_factory=dict)


class SupportsPing(Protocol):
    async def ping(self) -> bool: ...


class SupportsScalar(Protocol):
    async def execute_scalar(self) -> int: ...


async def probe(
    check: Callable[[], Awaitable[None]],
    *,
    # The bound is applied with asyncio.wait_for below; ASYNC109 assumes a
    # timeout parameter is passed down to a library call instead.
    timeout: float = DEFAULT_TIMEOUT_SECONDS,  # noqa: ASYNC109
) -> ComponentHealth:
    """Run one dependency check, converting any failure into a status."""
    started = asyncio.get_running_loop().time()
    try:
        await asyncio.wait_for(check(), timeout=timeout)
    except TimeoutError:
        return ComponentHealth(status=ComponentStatus.DOWN, detail="timeout")
    except Exception as exc:  # deliberately broad: a probe reports, never raises
        # Only the exception class name is reported: messages from drivers can
        # embed the DSN, which contains the password.
        return ComponentHealth(status=ComponentStatus.DOWN, detail=type(exc).__name__)
    elapsed_ms = int((asyncio.get_running_loop().time() - started) * 1000)
    return ComponentHealth(status=ComponentStatus.OK, latency_ms=elapsed_ms)


def aggregate(
    components: dict[str, ComponentHealth],
    *,
    service: str,
    version: str,
    app_env: str,
    now: datetime | None = None,
) -> HealthReport:
    statuses = {component.status for component in components.values()}
    if ComponentStatus.DOWN in statuses:
        overall = ComponentStatus.DOWN
    elif ComponentStatus.DEGRADED in statuses:
        overall = ComponentStatus.DEGRADED
    else:
        overall = ComponentStatus.OK

    return HealthReport(
        status=overall,
        service=service,
        version=version,
        app_env=app_env,
        checked_at=now or datetime.now(UTC),
        components=components,
    )
