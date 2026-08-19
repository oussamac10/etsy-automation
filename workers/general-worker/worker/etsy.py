"""Worker execution module for Etsy draft creation and asset dispatching."""

from __future__ import annotations

import uuid
import httpx
import structlog

from app.api.dependencies import build_credential_cipher
from app.application.etsy_draft import execute_etsy_draft_pipeline
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ProviderName
from app.domain.errors import EntityNotFoundError
from app.infrastructure.database import create_engine, create_session_factory
from app.ports.providers import EtsyGateway
from app.ports.telegram import TelegramGateway
from app.providers.etsy import EtsyProvider
from app.providers.fake import FakeEtsyProvider
from app.providers.s3 import S3ObjectStorage
from app.providers.telegram import FakeTelegramGateway, RealTelegramGateway
from app.settings import get_settings

logger = structlog.get_logger(__name__)


async def run_etsy_draft_pipeline_async(workflow_id: uuid.UUID) -> None:
    """Execute complete Etsy draft listing creation, mockups upload, and customer ZIP upload in worker."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )
    cipher = build_credential_cipher(settings)
    if cipher is None:
        raise RuntimeError("Credential encryption key is missing or invalid in worker.")

    try:
        async with UnitOfWork(session_factory) as uow:
            workflow = await uow.workflows.get(workflow_id)
            if workflow is None:
                raise EntityNotFoundError("ProductWorkflow", workflow_id)
            owner_id = workflow.owner_id

            # Initialize Etsy Gateway
            etsy_gateway: EtsyGateway
            if settings.provider_mode == "live" and settings.resolved_etsy_api_key:
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    etsy_gateway = EtsyProvider(
                        api_key=settings.resolved_etsy_api_key,
                        base_url=settings.etsy_api_base_url,
                        token_url=settings.etsy_token_url,
                        client=http_client,
                    )
                    # Initialize Telegram Gateway
                    bot_token = None
                    if settings.telegram_bot_token:
                        bot_token = settings.telegram_bot_token.get_secret_value()
                    else:
                        cred = await uow.credentials.get(owner_id, ProviderName.TELEGRAM)
                        if cred:
                            bot_token = cipher.decrypt(cred.ciphertext, key_version=cred.key_version)

                    tg_gateway: TelegramGateway
                    if bot_token:
                        tg_gateway = RealTelegramGateway(bot_token, http_client)
                    else:
                        tg_gateway = FakeTelegramGateway()

                    await execute_etsy_draft_pipeline(
                        workflow_id=workflow_id,
                        owner_id=owner_id,
                        uow=uow,
                        storage=storage,
                        cipher=cipher,
                        etsy_gateway=etsy_gateway,
                        telegram_gateway=tg_gateway,
                    )
            else:
                fake_etsy = FakeEtsyProvider()
                fake_tg = FakeTelegramGateway()
                await execute_etsy_draft_pipeline(
                    workflow_id=workflow_id,
                    owner_id=owner_id,
                    uow=uow,
                    storage=storage,
                    cipher=cipher,
                    etsy_gateway=fake_etsy,
                    telegram_gateway=fake_tg,
                )

            logger.info("etsy_draft_worker_pipeline_succeeded", workflow_id=str(workflow_id))

    except Exception as exc:
        logger.exception("etsy_draft_worker_pipeline_failed", workflow_id=str(workflow_id), error=str(exc))
        raise exc
    finally:
        await engine.dispose()
