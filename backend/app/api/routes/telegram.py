from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.application.telegram import handle_telegram_callback, handle_telegram_command
from app.application.unit_of_work import UnitOfWork
from app.infrastructure.logging import get_logger

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = get_logger("telegram_webhook")


async def process_webhook_update(payload: dict[str, Any], state: Any) -> None:
    update_id = payload.get("update_id")
    if not update_id:
        logger.warning("invalid_webhook_payload", reason="update_id missing")
        return

    # Check update ID duplicate in Redis
    redis_key = f"tg_processed_update:{update_id}"
    is_new = await state.redis.set(redis_key, "1", nx=True, ex=86400)
    if not is_new:
        logger.info("webhook_update_duplicate_ignored", update_id=update_id)
        return

    message = payload.get("message")
    callback_query = payload.get("callback_query")

    if callback_query:
        chat = callback_query.get("message", {}).get("chat")
        from_user = callback_query.get("from")
        data = callback_query.get("data")
        if not chat or not from_user or not data:
            logger.warning(
                "invalid_webhook_payload",
                reason="callback_query missing chat, from, or data",
            )
            return

        chat_id = chat.get("id")
        tg_user_id = from_user.get("id")
        username = from_user.get("username")
        if chat_id is None or tg_user_id is None:
            logger.warning(
                "invalid_webhook_payload",
                reason="chat_id or tg_user_id missing in callback",
            )
            return

        async with UnitOfWork(state.session_factory) as uow:
            try:
                response_text = await handle_telegram_callback(
                    uow=uow,
                    redis=state.redis,
                    telegram_user_id=tg_user_id,
                    telegram_chat_id=chat_id,
                    telegram_username=username,
                    callback_data=data,
                    now=datetime.now(UTC),
                )
                await state.telegram_gateway.send_message(
                    chat_id=chat_id,
                    text=response_text,
                )
            except Exception as exc:
                logger.exception(
                    "telegram_webhook_callback_failed",
                    update_id=update_id,
                    error=str(exc),
                )
        return

    if not message:
        logger.warning("invalid_webhook_payload", reason="message and callback_query missing")
        return

    chat = message.get("chat")
    from_user = message.get("from")
    text = message.get("text")
    if not chat or not from_user or not text:
        logger.warning("invalid_webhook_payload", reason="chat, from, or text missing")
        return

    chat_id = chat.get("id")
    tg_user_id = from_user.get("id")
    username = from_user.get("username")
    if chat_id is None or tg_user_id is None:
        logger.warning("invalid_webhook_payload", reason="chat_id or tg_user_id missing")
        return

    async with UnitOfWork(state.session_factory) as uow:
        try:
            response_text = await handle_telegram_command(
                uow=uow,
                redis=state.redis,
                http_client=state.http_client,
                engine=state.engine,
                settings=state.settings,
                telegram_gateway=state.telegram_gateway,
                telegram_user_id=tg_user_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
                text=text,
                now=datetime.now(UTC),
            )
            reply_markup = getattr(response_text, "reply_markup", None)
            await state.telegram_gateway.send_message(
                chat_id=chat_id,
                text=response_text,
                reply_markup=reply_markup,
            )
        except Exception as exc:
            logger.exception("telegram_webhook_command_failed", update_id=update_id, error=str(exc))


@router.post(
    "/webhook/{secret_token}",
    status_code=status.HTTP_200_OK,
    summary="Telegram webhook receiver",
)
async def telegram_webhook(
    secret_token: str,
    payload: dict[str, Any],
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    settings = request.app.state.settings

    # Verify secret token if configured
    configured_secret = settings.telegram_webhook_secret
    if configured_secret:
        expected = configured_secret.get_secret_value()
        if secret_token != expected and x_telegram_bot_api_secret_token != expected:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid secret token",
            )

    background_tasks.add_task(process_webhook_update, payload, request.app.state)
    return {"status": "queued"}
