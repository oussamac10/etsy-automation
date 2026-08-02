"""Health endpoints.

``/api/health`` is the aggregate readiness probe required by Phase 1: it
reports the API itself plus PostgreSQL, Redis and the Node image worker.
``/api/health/live`` is liveness only and never touches a dependency.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app import __version__
from app.infrastructure.checks import check_database, check_image_worker, check_redis
from app.infrastructure.health import ComponentStatus, aggregate
from app.settings import Settings, get_settings

router = APIRouter(tags=["health"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class ComponentHealthResponse(BaseModel):
    status: ComponentStatus
    detail: str | None = None
    latency_ms: int | None = None


class LivenessResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str
    version: str


class HealthResponse(BaseModel):
    status: ComponentStatus
    service: str
    version: str
    app_env: str
    checked_at: str
    components: dict[str, ComponentHealthResponse]


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
)
async def liveness(settings: SettingsDep) -> LivenessResponse:
    return LivenessResponse(status="ok", service="api", version=__version__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Readiness probe for the API and every dependency",
    responses={503: {"description": "At least one dependency is unavailable"}},
)
async def health(request: Request, response: Response, settings: SettingsDep) -> HealthResponse:
    state = request.app.state

    components = {
        "database": await check_database(state.engine),
        "redis": await check_redis(state.redis),
        "image_worker": await check_image_worker(state.http_client, settings.image_worker_url),
    }

    report = aggregate(
        components,
        service="api",
        version=__version__,
        app_env=settings.app_env,
    )

    if report.status is not ComponentStatus.OK:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=report.status,
        service=report.service,
        version=report.version,
        app_env=report.app_env,
        checked_at=report.checked_at.isoformat(),
        components={
            name: ComponentHealthResponse(
                status=component.status,
                detail=component.detail,
                latency_ms=component.latency_ms,
            )
            for name, component in report.components.items()
        },
    )
