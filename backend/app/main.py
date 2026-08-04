"""FastAPI application factory and process lifespan."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app import __version__
from app.api.dependencies import CSRF_HEADER, build_credential_cipher
from app.api.problems import register_exception_handlers
from app.api.routes import auth, health, telegram, workflow, workflows
from app.api.routes import settings as settings_routes
from app.infrastructure.database import create_engine, create_session_factory
from app.infrastructure.logging import configure_logging, get_logger
from app.settings import Settings, get_settings

CORRELATION_HEADER = "x-correlation-id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Accept or mint a correlation ID and echo it on every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Settings are injected so tests can vary them."""
    resolved = settings or get_settings()

    configure_logging(level=resolved.log_level, json_output=not resolved.is_local)
    logger = get_logger("app")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(resolved.database_url)
        redis_client: aioredis.Redis = aioredis.from_url(resolved.redis_url, decode_responses=True)
        http_client = httpx.AsyncClient(timeout=10.0)

        application.state.settings = resolved
        application.state.logger = logger
        application.state.engine = engine
        application.state.session_factory = create_session_factory(engine)
        application.state.redis = redis_client
        application.state.http_client = http_client
        # Built once. ``None`` when ENCRYPTION_KEY is unusable: the credential
        # endpoints then answer 503 instead of the whole API failing to start,
        # and nothing can fall back to storing a secret in the clear.
        cipher = build_credential_cipher(resolved)
        application.state.credential_cipher = cipher

        from app.ports.telegram import TelegramGateway
        from app.providers.telegram import FakeTelegramGateway, RealTelegramGateway

        telegram_gateway: TelegramGateway
        if resolved.provider_mode == "live" and resolved.telegram_bot_token:
            telegram_gateway = RealTelegramGateway(
                resolved.telegram_bot_token.get_secret_value(),
                http_client,
            )
        else:
            telegram_gateway = FakeTelegramGateway()
        application.state.telegram_gateway = telegram_gateway

        # Configure Dramatiq broker
        from worker.broker import configure_broker  # type: ignore[import-not-found]
        configure_broker(resolved.redis_url, resolved.queue_namespace)

        # Start Outbox Publisher
        import os
        outbox_publisher = None
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            from app.infrastructure.outbox_publisher import OutboxPublisher
            session_factory = create_session_factory(engine)
            outbox_publisher = OutboxPublisher(session_factory)
            outbox_publisher.start()

        logger.info(
            "api_started",
            app_env=resolved.app_env,
            provider_mode=resolved.provider_mode,
            # The key itself is never logged; whether one is usable is not secret.
            credential_encryption=("configured" if cipher else "unavailable"),
            version=__version__,
        )
        try:
            yield
        finally:
            if outbox_publisher:
                outbox_publisher.stop()
            await http_client.aclose()
            await redis_client.aclose()
            await engine.dispose()
            logger.info("api_stopped")

    application = FastAPI(
        title="Etsy PNG Automation API",
        version=__version__,
        description=(
            "Prepares original PNG products for an Etsy shop. Creates drafts only; "
            "it never publishes or activates a listing."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    application.state.logger = logger
    application.state.settings = resolved

    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "authorization",
            "content-type",
            CORRELATION_HEADER,
            "idempotency-key",
            # The browser sends the double-submit token on every mutation.
            CSRF_HEADER,
        ],
    )

    register_exception_handlers(application)

    application.include_router(health.router, prefix="/api")
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(settings_routes.router, prefix="/api/v1")
    application.include_router(workflow.router, prefix="/api/v1")
    application.include_router(workflows.router, prefix="/api/v1")
    application.include_router(telegram.router, prefix="/api/v1")

    return application


# Started with `uvicorn app.main:create_app --factory`. There is deliberately no
# module-level app instance: importing this module must not read the
# environment, so tests can build an app with their own settings.
