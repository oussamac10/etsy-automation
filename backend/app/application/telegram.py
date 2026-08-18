from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

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


class TelegramResponse(str):
    reply_markup: dict[str, Any] | None

    def __new__(cls, content: str, reply_markup: dict[str, Any] | None = None) -> TelegramResponse:
        obj = super().__new__(cls, content)
        obj.reply_markup = reply_markup
        return obj


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
            "generate a pairing code, and send it to this bot or click "
            "<code>/start &lt;code&gt;</code>."
        )

    if command == "/help":
        return (
            "<b>Available Commands:</b>\n"
            "• <code>/start</code> - Start or pair the bot\n"
            "• <code>/help</code> - List supported commands\n"
            "• <code>/status</code> - Show application and worker status\n"
            "• <code>/jobs</code> - List your recent automation jobs\n"
            "• <code>/job &lt;id&gt;</code> - Show details of a specific job\n"
            "• <code>/pause</code> - Pause automation dispatching\n"
            "• <code>/resume</code> - Resume automation dispatching\n"
            "• <code>/cancel &lt;id&gt;</code> - Cancel an active job\n"
            "• <code>/disconnect</code> - Disconnect Telegram bot"
        )

    if command == "/pair":
        if not arg or not arg.isdigit() or len(arg) != 6:
            return "Usage: <code>/pair &lt;code&gt;</code>"
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
            return "Usage: <code>/job &lt;job_id&gt;</code>"
        try:
            wf_uuid = uuid.UUID(job_id)
        except ValueError:
            return "Invalid Job ID format."

        workflow = await uow.workflows.get(wf_uuid)
        if workflow is None or workflow.owner_id != connection.user_id:
            return "Job not found."

        base_details = (
            "<b>Job Details:</b>\n"
            f"ID: <code>{workflow.id}</code>\n"
            f"Name: {escape_html(workflow.name)}\n"
            f"Marketplace: {workflow.target_marketplace}\n"
            f"Country: {workflow.target_country}\n"
            f"Language: {workflow.output_language}\n"
            f"State: <b>{workflow.state.value}</b>\n"
            f"Version: {workflow.version}"
        )

        if workflow.state == RunStatus.IDEA_REVIEW:
            concepts = await uow.concepts.list_for_workflow(workflow.id)
            lines = [
                base_details,
                "",
                "<b>Ranked Concepts (Gate 1):</b>",
            ]
            inline_keyboard = []
            for i, c in enumerate(concepts[:3]):
                score_val = c.score if c.score is not None else 0.0
                lines.append(
                    f"{i + 1}. <b>{escape_html(c.title)}</b> "
                    f"(Score: {score_val:.2f} | Risk: {c.risk_level.value})"
                )
                prompts = await uow.concepts.prompts(c.id)
                latest_prompt = prompts[-1] if prompts else None
                version = latest_prompt.version if latest_prompt else 1
                if latest_prompt:
                    prompt_txt = escape_html(latest_prompt.positive_prompt)
                    lines.append(f"Prompt: <code>{prompt_txt}</code>")
                inline_keyboard.append(
                    [
                        {
                            "text": f"Approve Concept {i + 1}",
                            "callback_data": f"approve:{c.id}:{version}",
                        }
                    ]
                )
            inline_keyboard.append(
                [
                    {
                        "text": "Reject All",
                        "callback_data": f"reject:{workflow.id}:{workflow.version}",
                    }
                ]
            )
            # Return custom TelegramResponse string subclass
            return TelegramResponse(
                "\n".join(lines),
                reply_markup={"inline_keyboard": inline_keyboard},
            )

        return base_details

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
            return "Usage: <code>/cancel &lt;job_id&gt;</code>"
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


async def handle_telegram_callback(
    uow: UnitOfWork,
    redis: aioredis.Redis,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: str | None,
    callback_data: str,
    now: datetime,
) -> str:
    """Process a Telegram callback query (from inline keyboard clicks)."""
    connection = await uow.telegram_connections.get_by_telegram_user_id(telegram_user_id)
    if connection is None or not connection.is_paired:
        return "This Telegram account is not paired with any project owner."

    user = await uow.users.get(connection.user_id)
    if user is None or not user.is_active:
        return "Unauthorized: Your account is disabled."

    parts = callback_data.split(":")
    action = parts[0]

    # Handle Concept Approval
    if action == "approve":
        if len(parts) < 3:
            return "Invalid callback data structure."
        concept_id_str = parts[1]
        version_str = parts[2]

        try:
            concept_id = uuid.UUID(concept_id_str)
            target_version = int(version_str)
        except ValueError:
            return "Invalid UUID or version format in callback."

        concept = await uow.concepts.get(concept_id)
        if not concept:
            return "Concept not found."

        workflow = await uow.workflows.get(concept.workflow_id)
        if not workflow or workflow.owner_id != connection.user_id:
            return "Workflow not found."

        from app.application import workflows as workflow_use_cases
        from app.domain.workflow import ApprovalDecision, ApprovalGate

        try:
            await workflow_use_cases.decide_gate(
                uow=uow,
                workflow_id=workflow.id,
                owner_id=connection.user_id,
                gate=ApprovalGate.IDEA_APPROVAL,
                decision=ApprovalDecision.APPROVED,
                actor=f"telegram:{telegram_user_id}",
                target_type="ProductConcept",
                target_id=concept_id,
                target_version=target_version,
                comment="Approved via Telegram remote control inline button",
            )
            return (
                f"Concept '<b>{escape_html(concept.title)}</b>' approved successfully! "
                "The idea was approved and is ready for the next phase."
            )
        except Exception as exc:
            return f"Failed to approve concept: {exc!s}"

    # Handle Concept Rejection
    elif action == "reject":
        if len(parts) < 3:
            return "Invalid callback data structure."
        workflow_id_str = parts[1]
        version_str = parts[2]

        try:
            workflow_id = uuid.UUID(workflow_id_str)
            target_version = int(version_str)
        except ValueError:
            return "Invalid UUID or version format in callback."

        workflow = await uow.workflows.get(workflow_id)
        if not workflow or workflow.owner_id != connection.user_id:
            return "Workflow not found."

        from app.application import workflows as workflow_use_cases
        from app.domain.workflow import ApprovalDecision, ApprovalGate

        try:
            await workflow_use_cases.decide_gate(
                uow=uow,
                workflow_id=workflow_id,
                owner_id=connection.user_id,
                gate=ApprovalGate.IDEA_APPROVAL,
                decision=ApprovalDecision.REJECTED,
                actor=f"telegram:{telegram_user_id}",
                target_type="ProductWorkflow",
                target_id=workflow_id,
                target_version=target_version,
                comment="Rejected via Telegram remote control inline button",
            )
            return f"Workflow campaign '<b>{escape_html(workflow.name)}</b>' has been rejected."
        except Exception as exc:
            return f"Failed to reject workflow: {exc!s}"

    # Handle Artwork Candidate Approval
    elif action == "art_app":
        if len(parts) < 2:
            return "Invalid callback data structure."
        asset_id_str = parts[1]

        try:
            asset_id = uuid.UUID(asset_id_str)
        except ValueError:
            return "Invalid UUID format in callback."

        asset = await uow.assets.get(asset_id)
        if not asset:
            return "Asset not found."

        workflow = await uow.workflows.get(asset.workflow_id)
        if not workflow or workflow.owner_id != connection.user_id:
            return "Workflow not found."

        from app.application import workflows as workflow_use_cases
        from app.domain.workflow import ApprovalDecision, ApprovalGate

        try:
            await workflow_use_cases.decide_gate(
                uow=uow,
                workflow_id=workflow.id,
                owner_id=connection.user_id,
                gate=ApprovalGate.ARTWORK_APPROVAL,
                decision=ApprovalDecision.APPROVED,
                actor=f"telegram:{telegram_user_id}",
                target_type="Asset",
                target_id=asset_id,
                target_version=None,
                comment="Approved via Telegram remote control inline button",
            )
            return (
                "Candidate artwork approved successfully! "
                "The workflow campaign is ready for production."
            )
        except Exception as exc:
            return f"Failed to approve artwork: {exc!s}"

    # Handle Artwork Candidate Rejection
    elif action == "art_rej":
        if len(parts) < 3:
            return "Invalid callback data structure."
        workflow_id_str = parts[1]
        version_str = parts[2]

        try:
            workflow_id = uuid.UUID(workflow_id_str)
            target_version = int(version_str)
        except ValueError:
            return "Invalid UUID or version format in callback."

        workflow = await uow.workflows.get(workflow_id)
        if not workflow or workflow.owner_id != connection.user_id:
            return "Workflow not found."

        from app.application import workflows as workflow_use_cases
        from app.domain.workflow import ApprovalDecision, ApprovalGate

        try:
            await workflow_use_cases.decide_gate(
                uow=uow,
                workflow_id=workflow_id,
                owner_id=connection.user_id,
                gate=ApprovalGate.ARTWORK_APPROVAL,
                decision=ApprovalDecision.REJECTED,
                actor=f"telegram:{telegram_user_id}",
                target_type="ProductWorkflow",
                target_id=workflow_id,
                target_version=target_version,
                comment="Rejected options via Telegram remote control inline button",
            )
            return (
                f"Artwork options for campaign '<b>{escape_html(workflow.name)}</b>' "
                "have been rejected."
            )
        except Exception as exc:
            return f"Failed to reject artwork options: {exc!s}"

    # Handle Artwork Candidate Regeneration
    elif action == "art_reg":
        if len(parts) < 2:
            return "Invalid callback data structure."
        workflow_id_str = parts[1]

        try:
            workflow_id = uuid.UUID(workflow_id_str)
        except ValueError:
            return "Invalid UUID format in callback."

        workflow = await uow.workflows.get(workflow_id)
        if not workflow or workflow.owner_id != connection.user_id:
            return "Workflow not found."

        from app.domain.enums import ConceptStatus, ProviderName
        from app.domain.workflow import JobStatus, RunStatus
        from app.infrastructure.models import ArtworkJob

        try:
            # 1. Transition workflow back to IDEA_APPROVED
            await uow.workflows.transition(
                workflow,
                to_state=RunStatus.IDEA_APPROVED,
                expected_version=workflow.version,
                reason="Regeneration requested via Telegram remote button",
                actor=f"telegram:{telegram_user_id}",
            )
            await uow.commit()

            # 2. Start standard artwork generation
            concepts = await uow.concepts.list_for_workflow(workflow_id)
            approved_concept = next(
                (c for c in concepts if c.status == ConceptStatus.APPROVED), None
            )
            if not approved_concept:
                return "No approved concept found to regenerate artwork from."

            prompts = await uow.concepts.prompts(approved_concept.id)
            if not prompts:
                return "Approved concept has no design prompts."
            latest_prompt = prompts[-1]

            provider_enum = ProviderName.RECRAFT
            model_val = "recraftv4_1"
            candidate_count = 4

            idempotency_key = f"art-{workflow_id}-{latest_prompt.id}-{candidate_count}-tg"

            # Create new ArtworkJob
            job = ArtworkJob(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                concept_id=approved_concept.id,
                prompt_id=latest_prompt.id,
                provider=provider_enum,
                provider_model=model_val,
                idempotency_key=idempotency_key,
                status=JobStatus.QUEUED,
                attempt_count=0,
                requested_width=1024,
                requested_height=1024,
                quality="standard",
            )
            await uow.artwork_jobs.add(job)

            # Transition workflow state to ART_QUEUED
            await uow.workflows.transition(
                workflow,
                to_state=RunStatus.ART_QUEUED,
                expected_version=workflow.version,
                reason="Triggered artwork generation via Telegram remote button",
                actor=f"telegram:{telegram_user_id}",
            )

            # Enqueue task via outbox
            await uow.outbox.add(
                "run_artwork_task",
                {"workflow_id": str(workflow_id), "job_id": str(job.id)},
            )
            await uow.commit()

            return (
                "Artwork generation enqueued successfully! "
                "You will receive another notification when complete."
            )
        except Exception as exc:
            return f"Failed to enqueue regeneration: {exc!s}"

    return "Unknown callback action."


async def send_telegram_notification(
    uow: UnitOfWork,
    telegram_gateway: TelegramGateway,
    owner_id: uuid.UUID,
    text: str,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    """Send a proactive notification to the owner's paired Telegram account."""
    connection = await uow.telegram_connections.get_by_user_id(owner_id)
    if connection and connection.is_paired and connection.telegram_chat_id is not None:
        await telegram_gateway.send_message(
            chat_id=connection.telegram_chat_id,
            text=text,
            reply_markup=reply_markup,
        )
