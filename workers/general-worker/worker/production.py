"""Orchestration for Phase 7 Print-Ready PNG Production & Realistic Mockups."""

from __future__ import annotations

import base64
import html
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.application.telegram import send_telegram_notification
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction, ConceptStatus, ProviderName
from app.domain.mockup_compositor import recomposite_workflow_mockups
from app.domain.mockup_products import get_requested_mockup_products
from app.domain.workflow import JobStatus, RunStatus
from app.infrastructure.models.artwork import Asset
from app.infrastructure.models.owner_settings import ProviderCredential
from app.ports.providers import ObjectStorage
from app.ports.telegram import TelegramGateway
from app.providers.telegram import FakeTelegramGateway, RealTelegramGateway
from app.settings import Settings


def escape_html(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    return html.escape(text, quote=False)


async def execute_production_pipeline(
    session_factory: Any,
    storage: ObjectStorage,
    settings: Settings,
    workflow_id: uuid.UUID,
    job_id: uuid.UUID,
    logger: Any,
) -> None:
    """Execute the end-to-end master PNG production pipeline."""
    # 1. Inspect and prepare job
    async with UnitOfWork(session_factory) as uow:
        job = await uow.production_jobs.get(job_id)
        if job is None:
            logger.error("production_job_not_found", job_id=str(job_id))
            return

        if job.status == JobStatus.SUCCEEDED:
            logger.info("production_job_already_succeeded", job_id=str(job_id))
            return

        workflow = await uow.workflows.get(workflow_id)
        if workflow is None:
            logger.error("workflow_not_found", workflow_id=str(workflow_id))
            return

        idea = await uow.ideas.get_for_workflow(workflow_id)
        workflow_name = idea.original_text[:40] if idea else f"Workflow {str(workflow_id)[:8]}"
        workflow_owner_id = workflow.owner_id
        source_asset_id = job.source_asset_id

        if not source_asset_id:
            assets = await uow.assets.list_for_workflow(workflow_id)
            artwork_assets = [a for a in assets if a.artwork_job_id is not None]
            if not artwork_assets:
                artwork_assets = [a for a in assets if not a.storage_key.startswith("production/")]
            if artwork_assets:
                source_asset_id = artwork_assets[0].id

        source_asset = await uow.assets.get(source_asset_id) if source_asset_id else None
        if not source_asset:
            raise RuntimeError(f"No source asset found for production job {job_id}")

        source_storage_key = source_asset.storage_key

        raw_uses = (
            workflow.intended_product_uses if workflow and workflow.intended_product_uses else None
        )
        concepts = await uow.concepts.list_for_workflow(workflow_id)
        approved_concept = next((c for c in concepts if c.status == ConceptStatus.APPROVED), None)
        exact_slogan: str | None = None
        typography_instructions: str | None = None

        if approved_concept:
            prompts = await uow.concepts.prompts(approved_concept.id)
            if prompts:
                latest_prompt = prompts[-1]
                exact_slogan = latest_prompt.exact_slogan
                typography_instructions = latest_prompt.typography_instructions
                if not raw_uses and latest_prompt.intended_product_uses:
                    raw_uses = latest_prompt.intended_product_uses

        intended_products: list[str] = get_requested_mockup_products(raw_uses)

        await uow.production_jobs.update(
            job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.now(UTC),
            attempt_count=job.attempt_count + 1,
        )
        await uow.audit.record(
            action=AuditAction.JOB_STATUS_CHANGED,
            entity_type="ProductionJob",
            entity_id=job_id,
            workflow_id=workflow_id,
            actor="system",
            summary="PNG Production Pipeline started.",
            after={"status": JobStatus.RUNNING.value},
        )
        await uow.commit()

    # 2. Fetch source artwork bytes
    source_bytes = await storage.get(source_storage_key)
    source_base64 = base64.b64encode(source_bytes).decode("utf-8")

    # 3. Call image-worker microservice
    image_worker_url = settings.image_worker_url.rstrip("/")
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        res = await http_client.post(
            f"{image_worker_url}/pipeline/process-master",
            json={
                "image_base64": source_base64,
                "exact_slogan": exact_slogan,
                "typography_instructions": typography_instructions,
                "intended_products": intended_products,
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"Image worker returned {res.status_code}: {res.text}")
        pipeline_data = res.json()

    master_b64 = pipeline_data["master_png_base64"]
    master_bytes = base64.b64decode(master_b64)
    qa_report = pipeline_data["qa_report"]
    qa_passed = qa_report.get("qa_passed", False)

    # 4. Upload Master PNG to Storage
    master_storage_key = f"production/{workflow_id}/{job_id}/master.png"
    stored_master = await storage.put(master_storage_key, master_bytes, "image/png")

    # 5. Persist Master Asset, Recomposite User Mockups, and Finalize Job Status
    async with UnitOfWork(session_factory) as uow:
        existing_master = await uow.assets.get_by_checksum_sha256(workflow_id, stored_master.sha256)
        if existing_master is not None:
            master_asset_id = existing_master.id
        else:
            master_asset_id = uuid.uuid4()
            master_asset = Asset(
                id=master_asset_id,
                workflow_id=workflow_id,
                artwork_job_id=None,
                derived_from_id=source_asset_id,
                storage_key=stored_master.storage_key,
                mime_type="image/png",
                byte_size=stored_master.byte_size,
                checksum_sha256=stored_master.sha256,
                width=qa_report.get("width", 4500),
                height=qa_report.get("height", 5400),
                has_alpha=True,
                has_transparent_pixels=True,
                quality_check=qa_report,
                provenance={
                    "pipeline": "image-pipeline@0.1.0",
                    "profile": "etsy-png-standard",
                    "source_asset_id": str(source_asset_id),
                    "typography_applied": pipeline_data.get("typography_applied", False),
                    "slogan": exact_slogan,
                },
            )
            await uow.assets.add(master_asset)

        # 5b. Recomposite existing user-uploaded library mockups
        try:
            workflow = await uow.workflows.get(workflow_id)
            if workflow:
                await recomposite_workflow_mockups(
                    uow=uow,
                    storage=storage,
                    workflow_id=workflow_id,
                    master_bytes=master_bytes,
                    master_asset_id=master_asset_id,
                    owner_id=workflow.owner_id,
                    image_worker_url=settings.image_worker_url,
                )
        except Exception as recomp_exc:
            logger.warning("failed_to_recomposite_existing_mockups", error=str(recomp_exc))

        # 5c. Mark ProductionJob terminal status and update workflow state
        await uow.production_jobs.update(
            job_id,
            status=JobStatus.SUCCEEDED if qa_passed else JobStatus.FAILED,
            output_asset_id=master_asset_id,
            qa_report=qa_report,
            qa_passed=qa_passed,
            failure_kind=None if qa_passed else "QA_FAILED",
            failure_message=None if qa_passed else "Master PNG failed QA validation checks",
            completed_at=datetime.now(UTC),
        )

        workflow = await uow.workflows.get(workflow_id)
        if workflow and workflow.state == RunStatus.PRODUCTION:
            await uow.workflows.transition(
                workflow,
                to_state=RunStatus.ARTWORK_APPROVED,
                expected_version=workflow.version,
                reason="PNG production pipeline completed successfully",
                actor="system",
            )

        await uow.audit.record(
            action=AuditAction.JOB_STATUS_CHANGED,
            entity_type="ProductionJob",
            entity_id=job_id,
            workflow_id=workflow_id,
            actor="system",
            summary="PNG Production Pipeline completed successfully.",
            after={
                "status": JobStatus.SUCCEEDED.value if qa_passed else JobStatus.FAILED.value,
                "output_asset_id": str(master_asset_id),
                "qa_passed": qa_passed,
            },
        )
        await uow.commit()

    # 6. Telegram notification
    try:
        dash_origins = settings.cors_origins
        dash_base = dash_origins[0] if dash_origins else "http://localhost:3000"
        master_signed_url = await storage.signed_url(stored_master.storage_key, 3600)
        inline_buttons = []
        if dash_base.startswith("https://") and "localhost" not in dash_base:
            inline_buttons.append(
                [{"text": "Open Dashboard", "url": f"{dash_base}/workflow/{workflow_id}"}]
            )
        if master_signed_url.startswith("https://") and "localhost" not in master_signed_url:
            inline_buttons.append([{"text": "Download Master PNG", "url": master_signed_url}])

        reply_markup = {"inline_keyboard": inline_buttons} if inline_buttons else None
        qa_icon = "✅" if qa_passed else "⚠️"
        typo_status = "Applied" if pipeline_data.get("typography_applied") else "None"
        notify_text = (
            f"✨ <b>PNG Production Complete!</b>\n\n"
            f"Workflow: <b>{escape_html(workflow_name)}</b>\n"
            f"Master Profile: <code>4500x5400 px @ 300 DPI</code>\n"
            f"QA Report: {qa_icon} <b>{'PASSED' if qa_passed else 'WARNINGS'}</b>\n"
            f"Slogan Typography: <b>{typo_status}</b>\n\n"
            f'• <a href="{master_signed_url}">Master PNG Preview</a>\n\n'
            f"Print-ready master asset is ready. You can now create realistic product mockups."
        )

        bot_token = None
        if settings.telegram_bot_token:
            bot_token = settings.telegram_bot_token.get_secret_value()
        elif settings.provider_mode == "live":
            try:
                from sqlalchemy import select

                from app.api.dependencies import build_credential_cipher

                cipher = build_credential_cipher(settings)
                if cipher:
                    async with session_factory() as session:
                        stmt = (
                            select(ProviderCredential)
                            .where(ProviderCredential.provider == ProviderName.TELEGRAM)
                            .limit(1)
                        )
                        result = await session.execute(stmt)
                        cred = result.scalar_one_or_none()
                        if cred:
                            bot_token = cipher.decrypt(
                                cred.ciphertext, key_version=cred.key_version
                            )
            except Exception as e:
                logger.debug("bot_token_resolution_skipped", error=str(e))

        if settings.provider_mode == "live" and bot_token:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                tg_gateway: TelegramGateway = RealTelegramGateway(bot_token, http_client)
                async with UnitOfWork(session_factory) as uow:
                    await send_telegram_notification(
                        uow, tg_gateway, workflow_owner_id, notify_text, reply_markup
                    )
        else:
            fake_gateway: TelegramGateway = FakeTelegramGateway()
            async with UnitOfWork(session_factory) as uow:
                await send_telegram_notification(
                    uow, fake_gateway, workflow_owner_id, notify_text, reply_markup
                )
    except Exception as notify_err:
        logger.warning("production_notification_failed", error=str(notify_err))
