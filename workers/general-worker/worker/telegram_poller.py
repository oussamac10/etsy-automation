from __future__ import annotations

import asyncio
import logging
import signal
from datetime import UTC, datetime
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.application.telegram import handle_telegram_command
from app.application.unit_of_work import UnitOfWork
from app.infrastructure.database import create_engine, create_session_factory
from app.infrastructure.logging import configure_logging, get_logger
from app.providers.telegram import FakeTelegramGateway, RealTelegramGateway
from app.settings import get_settings

logger = get_logger("telegram_poller")

running = True


def handle_shutdown(signum: Any, frame: Any) -> None:
    global running
    logger.info("Shutdown signal received, stopping poller...")
    running = False


async def run_poller() -> None:
    global running
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=not settings.is_local)

    logger.info("Starting Telegram Bot Poller", provider_mode=settings.provider_mode)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    http_client = httpx.AsyncClient(timeout=10.0)

    if settings.provider_mode == "live" and settings.telegram_bot_token:
        gateway = RealTelegramGateway(
            settings.telegram_bot_token.get_secret_value(),
            http_client,
        )
    else:
        logger.info("Using Fake Telegram Gateway for polling")
        gateway = FakeTelegramGateway()

    # Retrieve stored offset
    offset_str = await redis_client.get("tg_bot_offset")
    offset = int(offset_str) if offset_str else None

    # Register signals
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    retry_delay = 1.0
    max_retry_delay = 60.0

    while running:
        try:
            updates = await gateway.get_updates(offset=offset, timeout=10)
            retry_delay = 1.0

            for update in updates:
                if not running:
                    break

                update_id = update.get("update_id")
                if update_id is None:
                    continue

                redis_key = f"tg_processed_update:{update_id}"
                is_new = await redis_client.set(redis_key, "1", nx=True, ex=86400)
                if not is_new:
                    offset = update_id + 1
                    await redis_client.set("tg_bot_offset", str(offset))
                    continue

                message = update.get("message")
                if message and message.get("text"):
                    chat = message.get("chat")
                    from_user = message.get("from")
                    text = message.get("text")
                    if chat and from_user and text:
                        chat_id = chat.get("id")
                        tg_user_id = from_user.get("id")
                        username = from_user.get("username")

                        if chat_id is not None and tg_user_id is not None:
                            logger.info(
                                "Processing command in poller",
                                command=text,
                                username=username,
                            )
                            async with UnitOfWork(session_factory) as uow:
                                try:
                                    response_text = await handle_telegram_command(
                                        uow=uow,
                                        redis=redis_client,
                                        http_client=http_client,
                                        engine=engine,
                                        settings=settings,
                                        telegram_gateway=gateway,
                                        telegram_user_id=tg_user_id,
                                        telegram_chat_id=chat_id,
                                        telegram_username=username,
                                        text=text,
                                        now=datetime.now(UTC),
                                    )
                                    await gateway.send_message(
                                        chat_id=chat_id,
                                        text=response_text,
                                    )
                                except Exception as exc:
                                    logger.error(
                                        "Error processing Telegram command in poller",
                                        exc_info=exc,
                                    )

                offset = update_id + 1
                await redis_client.set("tg_bot_offset", str(offset))

            await asyncio.sleep(0.5)

        except Exception as exc:
            logger.error("Error fetching updates from Telegram", exc_info=exc)
            if not running:
                break
            logger.info(f"Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2.0, max_retry_delay)

    logger.info("Cleaning up and shutting down poller...")
    await http_client.aclose()
    await redis_client.aclose()
    await engine.dispose()
    logger.info("Poller stopped.")


if __name__ == "__main__":
    asyncio.run(run_poller())
