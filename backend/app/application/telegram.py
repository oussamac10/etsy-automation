from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.owner_settings import get_or_create_settings
from app.application.unit_of_work import UnitOfWork
from app.application.workflows import transition_workflow
from app.domain.enums import AuditAction
from app.domain.workflow import RunStatus
from app.infrastructure.checks import check_database, check_image_worker, check_redis
from app.ports.telegram import TelegramGateway
from app.providers.telegram import escape_html
from app.settings import Settings


async def generate_pairing_code(uow: UnitOfWork, owner_id: uuid.UUID) -> tuple[str, datetime]:
    """Generate a short-lived 6-digit pairing code and save its hash."""
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(minutes=5)

    await uow.telegram_connections.create_or_update_pairing_code(
        user_id=owner_id,
        code_hash=code_hash,
        expires_at=expires_at,
    )
    await uow.commit()
    return code, expires_at


async def disconnect_telegram(uow: UnitOfWork, owner_id: uuid.UUID) -> None:
    """Revoke the Telegram connection for the owner."""
    record = await uow.telegram_connections.get_by_user_id(owner_id)
    if record is not None:
        await uow.telegram_connections.disconnect(record, revoked_at=datetime.now(UTC))
        await uow.audit.record(
            action=AuditAction.TELEGRAM_DISCONNECTED,
            entity_type="TelegramConnection",
            entity_id=record.id,
            actor=str(owner_id),
            summary="Telegram connection revoked from web settings",
        )
        await uow.commit()


async def handle_telegram_command(
    uow: UnitOfWork,
    redis: aioredis.Redis,
    http_client: httpx.AsyncClient,
    engine: AsyncEngine,
    settings: Settings,
    telegram_gateway: TelegramGateway,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: str | None,
    text: str,
    now: datetime,
) -> str:
    """Process a single Telegram command or pairing code and return HTML formatted response."""
    cleaned = text.strip()
    if not cleaned:
        return "Please send a command or code."

    # Standard command parsing
    if cleaned.startswith("/"):
        parts = cleaned.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
    elif cleaned.isdigit() and len(cleaned) == 6:
        command = "/pair"
        arg = cleaned
    else:
        command = cleaned.lower()
        arg = ""

    # Command: Start / Help / Pair (Unpaired or pairing flow)
    if command == "/start":
        # Check if deep linking with a pairing code: e.g., /start 123456
        if arg.isdigit() and len(arg) == 6:
            return await _pair_flow(
                uow, redis, arg, telegram_user_id, telegram_chat_id, telegram_username, now
            )

        connection = await uow.telegram_connections.get_by_telegram_user_id(telegram_user_id)
        if connection is not None and connection.is_paired:
            return (
                "You are already connected to Etsy Automation. "
                "Send `/help` to see the list of supported commands."
            )
        return (
            "Welcome to <b>Etsy Automation Bot</b>!\n\n"
            "To connect your account, please go to the Settings section on your web dashboard, "
            "generate a pairing code, and send it to this bot or click `/start <code>`."
        )

    if command == "/help":
        return (
            "<b>Available Commands:</b>\n"
            "• `/start` - Start or pair the bot\n"
            "• `/help` - List supported commands\n"
            "• `/status` - Show application and worker status\n"
            "• `/jobs` - List your recent automation jobs\n"
            "• `/job <id>` - Show details of a specific job\n"
            "• `/pause` - Pause automation dispatching\n"
            "• `/resume` - Resume automation dispatching\n"
            "• `/cancel <id>` - Cancel an active job\n"
            "• `/disconnect` - Disconnect Telegram bot"
        )

    if command == "/pair":
        if not arg or not arg.isdigit() or len(arg) != 6:
            return "Usage: `/pair <code>`"
        return await _pair_flow(
            uow, redis, arg, telegram_user_id, telegram_chat_id, telegram_username, now
        )

    # All other commands require pairing and active account verification
    connection = await uow.telegram_connections.get_by_telegram_user_id(telegram_user_id)
    if connection is None or not connection.is_paired:
        return (
            "This Telegram account is not paired with any project owner. "
            "Please obtain a pairing code from the web settings dashboard and send it here."
        )

    user = await uow.users.get(connection.user_id)
    if user is None or not user.is_active:
        return "Unauthorized: Your account is disabled."

    if command == "/status":
        settings_row = await get_or_create_settings(uow, connection.user_id)
        paused_status = "PAUSED" if settings_row.is_paused else "ACTIVE"

        db_health = await check_database(engine)
        redis_health = await check_redis(redis)
        iw_health = await check_image_worker(http_client, settings.image_worker_url)

        return (
            "<b>Etsy PNG Automation Status</b>\n\n"
            f"Automation Dispatcher: <b>{paused_status}</b>\n"
            f"Database: <b>{db_health.status.value}</b>\n"
            f"Redis Queue: <b>{redis_health.status.value}</b>\n"
            f"Image Worker: <b>{iw_health.status.value}</b>"
        )

    if command == "/jobs":
        workflows = await uow.workflows.list(owner_id=connection.user_id, limit=10)
        if not workflows:
            return "You have no active or past automation jobs."

        lines = ["<b>Your Automation Jobs:</b>"]
        for w in workflows:
            lines.append(f"• <code>{w.id}</code> - {escape_html(w.name)} (<b>{w.state.value}</b>)")
        return "\n".join(lines)

    if command == "/job":
        job_id = arg.strip()
        if not job_id:
            return "Usage: `/job <job_id>`"
        try:
            wf_uuid = uuid.UUID(job_id)
        except ValueError:
            return "Invalid Job ID format."

        workflow = await uow.workflows.get(wf_uuid)
        if workflow is None or workflow.owner_id != connection.user_id:
            return "Job not found."

        return (
            "<b>Job Details:</b>\n"
            f"ID: <code>{workflow.id}</code>\n"
            f"Name: {escape_html(workflow.name)}\n"
            f"Marketplace: {workflow.target_marketplace}\n"
            f"Country: {workflow.target_country}\n"
            f"Language: {workflow.output_language}\n"
            f"State: <b>{workflow.state.value}</b>\n"
            f"Version: {workflow.version}"
        )

    if command == "/pause":
        settings_row = await get_or_create_settings(uow, connection.user_id)
        if settings_row.is_paused:
            return "Automation dispatching is already paused."
        settings_row.is_paused = True
        await uow.audit.record(
            action=AuditAction.SETTINGS_UPDATED,
            entity_type="OwnerSettings",
            entity_id=settings_row.id,
            actor="telegram",
            summary="Paused automation jobs via Telegram",
            before={"is_paused": False},
            after={"is_paused": True},
        )
        await uow.commit()
        return "Automation dispatching has been <b>PAUSED</b> for your account."

    if command == "/resume":
        settings_row = await get_or_create_settings(uow, connection.user_id)
        if not settings_row.is_paused:
            return "Automation dispatching is already active."
        settings_row.is_paused = False
        await uow.audit.record(
            action=AuditAction.SETTINGS_UPDATED,
            entity_type="OwnerSettings",
            entity_id=settings_row.id,
            actor="telegram",
            summary="Resumed automation jobs via Telegram",
            before={"is_paused": True},
            after={"is_paused": False},
        )
        await uow.commit()
        return "Automation dispatching has been <b>RESUMED</b> for your account."

    if command == "/cancel":
        job_id = arg.strip()
        if not job_id:
            return "Usage: `/cancel <job_id>`"
        try:
            wf_uuid = uuid.UUID(job_id)
        except ValueError:
            return "Invalid Job ID format."

        workflow = await uow.workflows.get(wf_uuid)
        if workflow is None or workflow.owner_id != connection.user_id:
            return "Job not found."

        if workflow.state in (RunStatus.CANCELLED, RunStatus.PUBLISHED):
            return (
                "Job cannot be cancelled because it is in a terminal state: "
                f"{workflow.state.value}."
            )

        await transition_workflow(
            uow,
            workflow_id=workflow.id,
            owner_id=connection.user_id,
            to_state=RunStatus.CANCELLED,
            expected_version=workflow.version,
            reason="Cancelled via Telegram command",
            actor="telegram",
        )
        return f"Job <code>{workflow.id}</code> has been successfully <b>CANCELLED</b>."

    if command == "/disconnect":
        await uow.telegram_connections.disconnect(connection, revoked_at=now)
        await uow.audit.record(
            action=AuditAction.TELEGRAM_DISCONNECTED,
            entity_type="TelegramConnection",
            entity_id=connection.id,
            actor=str(connection.user_id),
            summary="Telegram connection revoked via Telegram command",
        )
        await uow.commit()
        return "Your Telegram account has been successfully disconnected from Etsy Automation."

    return "Unknown command. Send `/help` for a list of supported commands."


async def _pair_flow(
    uow: UnitOfWork,
    redis: aioredis.Redis,
    code: str,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: str | None,
    now: datetime,
) -> str:
    """Rate-limited pairing verification."""
    redis_key = f"tg_pair_attempts:{telegram_user_id}"
    attempts_str = await redis.get(redis_key)
    attempts = int(attempts_str) if attempts_str else 0

    if attempts >= 3:
        return "Too many failed attempts. Please generate a new code on the web settings page."

    code_hash = hashlib.sha256(code.encode()).hexdigest()
    record = await uow.telegram_connections.get_by_pairing_code_hash(code_hash)

    if record is None:
        await redis.set(redis_key, attempts + 1, ex=300)
        return "Invalid pairing code. Please check the code and try again."

    if record.pairing_code_expires_at is None or record.pairing_code_expires_at < now:
        await redis.set(redis_key, attempts + 1, ex=300)
        return "Pairing code has expired. Please generate a new code on the web settings page."

    # Valid pairing: execute connection
    await uow.telegram_connections.pair(
        record,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        telegram_username=telegram_username,
        paired_at=now,
    )
    await uow.audit.record(
        action=AuditAction.TELEGRAM_PAIRED,
        entity_type="TelegramConnection",
        entity_id=record.id,
        actor=str(record.user_id),
        summary=f"Telegram bot paired with account (User ID: {telegram_user_id})",
    )
    await uow.commit()
    await redis.delete(redis_key)

    return "Successfully connected! You can now use the remote control commands."
