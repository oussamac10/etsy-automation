"""Etsy draft creation and asset dispatch application service.

Guarantees:
- CRITICAL SAFETY: Strictly forces draft state (`state="draft"`). Zero publish or activation capability.
- Full Idempotency: Reconciles existing Etsy listings and uploaded assets across worker retries and partial failures.
- Deterministic asset ordering: Primary mockup -> additional mockups -> customer digital ZIP package.
- State Machine integration: Transitions workflow from `READY_FOR_ETSY_DRAFT` to `ETSY_DRAFT_CREATED`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
import structlog

from app.application.etsy_auth import get_valid_access_token
from app.application.package import CustomerPackageService
from app.application.telegram import send_telegram_notification
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.domain.errors import DomainError, EntityNotFoundError
from app.domain.package_builder import create_access_delivery_pdf
from app.domain.production_resolver import (
    filter_active_user_mockups,
    get_production_master_asset,
)
from app.domain.tags import validate_listing_title, validate_tags
from app.domain.workflow import RunStatus
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
    ShopConnection,
)
from app.infrastructure.security import CredentialCipher
from app.ports.errors import ProviderError
from app.ports.providers import (
    EtsyGateway,
    EtsyListingDraftInput,
    ObjectStorage,
)
from app.ports.telegram import TelegramGateway
from app.providers.telegram import escape_html

logger = structlog.get_logger(__name__)


def build_etsy_shop_manager_url(listing_id: str) -> str:
    """Generate safe official Etsy Shop Manager listing editor URL."""
    return f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}"


async def validate_pre_dispatch(
    workflow_id: uuid.UUID,
    owner_id: uuid.UUID,
    uow: UnitOfWork,
    storage: ObjectStorage,
) -> tuple[ProductWorkflow, ListingDraft, ShopConnection, Asset, Asset]:
    """Validate all requirements before creating an Etsy draft listing.

    Validates:
    - Workflow ownership & state (`READY_FOR_ETSY_DRAFT`)
    - Active Etsy shop connection
    - Listing draft title, description, and exactly 13 tags
    - Production master PNG asset existence
    - Customer download ZIP package existence (or builds it)
    """
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)
    if workflow.owner_id != owner_id:
        raise DomainError("Workflow does not belong to the current owner.")

    if workflow.state != RunStatus.READY_FOR_ETSY_DRAFT and workflow.state != RunStatus.ETSY_DRAFT_CREATED:
        raise DomainError(
            f"Workflow state must be 'READY_FOR_ETSY_DRAFT' (Gate 3 approved) before creating an Etsy draft. "
            f"Current state: '{workflow.state}'."
        )

    # Validate Etsy Connection
    conn = await uow.shop_connections.get_by_user_id(owner_id)
    if conn is None or not conn.is_connected:
        raise DomainError("No active Etsy shop connection found. Please connect your Etsy shop in Settings.")

    # Validate Listing Draft
    listing = await uow.listing_drafts.get_by_workflow(workflow_id)
    if listing is None:
        raise EntityNotFoundError("ListingDraft", workflow_id)

    # Validate title & tags
    title_valid, title_err = validate_listing_title(listing.title)
    if not title_valid:
        raise DomainError(f"Invalid Etsy listing title: {title_err}")

    if not listing.description or not listing.description.strip():
        raise DomainError("Etsy listing description is empty.")

    tags_valid, accepted_tags, tags_err = validate_tags(listing.tags)
    if not tags_valid:
        raise DomainError(f"Invalid Etsy listing tags: {', '.join(tags_err)}")

    # Validate / Resolve Master PNG
    master_asset = await get_production_master_asset(uow, workflow_id)
    if master_asset is None:
        raise DomainError("Master print-ready PNG asset is missing. Complete asset production before dispatching to Etsy.")

    # Validate / Resolve Customer Package ZIP
    assets = await uow.assets.list_for_workflow(workflow_id)
    zip_asset = next(
        (
            a
            for a in assets
            if a.mime_type == "application/zip"
            or (a.provenance and a.provenance.get("kind") == "customer_package")
            or a.storage_key.endswith(".zip")
        ),
        None,
    )
    if zip_asset is None:
        # Build customer download package if not already assembled
        package_service = CustomerPackageService(storage)
        zip_asset = await package_service.build_customer_package(workflow_id, uow)

    return workflow, listing, conn, master_asset, zip_asset


async def execute_etsy_draft_pipeline(
    workflow_id: uuid.UUID,
    owner_id: uuid.UUID,
    uow: UnitOfWork,
    storage: ObjectStorage,
    cipher: CredentialCipher,
    etsy_gateway: EtsyGateway,
    telegram_gateway: TelegramGateway | None = None,
    web_dashboard_url: str = "http://localhost:3000",
) -> ListingDraft:
    """Orchestrate idempotent draft listing creation and asset upload to Etsy Open API v3."""
    workflow, listing, conn, master_asset, zip_asset = await validate_pre_dispatch(
        workflow_id=workflow_id,
        owner_id=owner_id,
        uow=uow,
        storage=storage,
    )

    # Get decrypted OAuth access token (auto-refreshes if within buffer)
    access_token = await get_valid_access_token(
        uow=uow,
        cipher=cipher,
        etsy_gateway=etsy_gateway,
        owner_id=owner_id,
    )

    try:
        # Step 1: Create Etsy Draft Listing (Idempotent)
        listing_id = listing.etsy_listing_id
        if not listing_id:
            await uow.listing_drafts.update_etsy_dispatch_status(
                listing.id, status="creating_listing"
            )
            await uow.commit()

            price_cents = listing.price_minor_units if listing.price_minor_units is not None else 499

            payload = EtsyListingDraftInput(
                title=listing.title,
                description=listing.description,
                tags=list(listing.tags),
                price_cents=price_cents,
                currency=listing.currency or "USD",
                taxonomy_id=listing.taxonomy_id or 1049,  # Default Digital Prints
                who_made="i_did",
                when_made="2020_2026",
                item_type="download",
                is_supply=False,
                quantity=999,
            )

            create_resp = await etsy_gateway.create_draft_listing(
                access_token=access_token,
                shop_id=conn.etsy_shop_id,
                listing=payload,
                idempotency_key=str(workflow_id),
            )
            listing_id = create_resp.listing_id
            management_url = build_etsy_shop_manager_url(listing_id)

            listing = await uow.listing_drafts.update_etsy_draft(
                listing.id,
                etsy_shop_id=conn.etsy_shop_id,
                etsy_listing_id=listing_id,
                etsy_listing_url=management_url,
                etsy_state="draft",
                etsy_draft_created_at=datetime.now(UTC),
                etsy_dispatch_status="creating_listing",
            )
            await uow.commit()

            logger.info(
                "etsy_draft_listing_created",
                workflow_id=str(workflow_id),
                listing_id=listing_id,
                shop_id=conn.etsy_shop_id,
            )

        # Step 2: Upload Preview Images in Deterministic Order
        await uow.listing_drafts.update_etsy_dispatch_status(
            listing.id, status="uploading_images"
        )
        await uow.commit()

        assets = await uow.assets.list_for_workflow(workflow_id)
        mockups = filter_active_user_mockups(assets, master_asset.id)

        # If no active user mockups, use master preview image as fallback preview
        preview_assets = mockups if mockups else [master_asset]

        current_image_ids = list(listing.etsy_image_ids or [])

        for rank, asset in enumerate(preview_assets[:10], start=1):
            # Check if this rank was already uploaded (if stored count >= rank)
            if len(current_image_ids) >= rank:
                continue

            try:
                img_bytes = await storage.get(asset.storage_key)
                filename = f"preview_{rank}.png" if asset.mime_type == "image/png" else f"preview_{rank}.jpg"
                img_resp = await etsy_gateway.upload_listing_image(
                    access_token=access_token,
                    shop_id=conn.etsy_shop_id,
                    listing_id=listing_id,
                    image_bytes=img_bytes,
                    filename=filename,
                    rank=rank,
                    alt_text=f"{listing.title} - Preview {rank}",
                )
                listing = await uow.listing_drafts.record_etsy_image_upload(
                    listing.id, image_id=img_resp.listing_image_id
                )
                current_image_ids.append(img_resp.listing_image_id)
                await uow.commit()
                logger.info(
                    "etsy_listing_image_uploaded",
                    workflow_id=str(workflow_id),
                    listing_id=listing_id,
                    image_id=img_resp.listing_image_id,
                    rank=rank,
                )
            except Exception as exc:
                logger.warning(
                    "etsy_image_upload_partial_failure",
                    workflow_id=str(workflow_id),
                    rank=rank,
                    error=str(exc),
                )
                raise

        # Step 3: Upload Customer Digital Download ZIP Package
        await uow.listing_drafts.update_etsy_dispatch_status(
            listing.id, status="uploading_file"
        )
        await uow.commit()

        if not listing.etsy_file_id:
            zip_bytes = await storage.get(zip_asset.storage_key)
            max_etsy_bytes = 20 * 1024 * 1024  # 20MB Etsy Open API v3 limit

            if len(zip_bytes) <= max_etsy_bytes:
                file_resp = await etsy_gateway.upload_listing_file(
                    access_token=access_token,
                    shop_id=conn.etsy_shop_id,
                    listing_id=listing_id,
                    file_bytes=zip_bytes,
                    filename="digital-package.zip",
                    rank=1,
                )
            else:
                logger.info(
                    "package_exceeds_etsy_limit_generating_access_pdf",
                    workflow_id=str(workflow_id),
                    size_bytes=len(zip_bytes),
                )
                download_url = await storage.signed_url(zip_asset.storage_key, expires_in_seconds=604800)
                shop_name = conn.etsy_shop_name or "Digital Art Studio"
                access_pdf_bytes = create_access_delivery_pdf(
                    listing_title=listing.title or "High-Resolution Digital Artwork",
                    shop_name=shop_name,
                    download_url=download_url,
                )
                file_resp = await etsy_gateway.upload_listing_file(
                    access_token=access_token,
                    shop_id=conn.etsy_shop_id,
                    listing_id=listing_id,
                    file_bytes=access_pdf_bytes,
                    filename="Digital_Download_Access_Instructions.pdf",
                    rank=1,
                )

            listing = await uow.listing_drafts.record_etsy_file_upload(
                listing.id, file_id=file_resp.listing_file_id
            )
            await uow.commit()
            logger.info(
                "etsy_digital_file_uploaded",
                workflow_id=str(workflow_id),
                listing_id=listing_id,
                file_id=file_resp.listing_file_id,
            )

        # Step 4: Finalize Workflow & Audit
        now = datetime.now(UTC)
        if workflow.state == RunStatus.READY_FOR_ETSY_DRAFT:
            await uow.workflows.transition(
                workflow,
                to_state=RunStatus.ETSY_DRAFT_CREATED,
                expected_version=workflow.version,
                reason="Etsy draft listing created successfully with mockups and customer ZIP bundle.",
                actor="system",
            )

        listing = await uow.listing_drafts.update_etsy_dispatch_status(
            listing.id,
            status="completed",
            last_synced_at=now,
        )

        await uow.audit.record(
            action=AuditAction.ETSY_DRAFT_CREATED,
            entity_type="ListingDraft",
            entity_id=listing.id,
            workflow_id=workflow_id,
            actor=str(owner_id),
            summary=f"Etsy draft listing created (ID: {listing_id}) in shop '{conn.etsy_shop_name}'.",
            metadata={
                "etsy_listing_id": listing_id,
                "etsy_shop_id": conn.etsy_shop_id,
                "etsy_shop_name": conn.etsy_shop_name,
                "image_count": len(listing.etsy_image_ids or []),
                "file_uploaded": bool(listing.etsy_file_id),
                "etsy_management_url": build_etsy_shop_manager_url(listing_id),
            },
        )
        await uow.commit()

        # Step 5: Telegram Completion Notification
        if telegram_gateway is not None:
            await send_etsy_draft_created_notification(
                uow=uow,
                telegram_gateway=telegram_gateway,
                owner_id=owner_id,
                workflow_id=workflow_id,
                title=listing.title,
                shop_name=conn.etsy_shop_name,
                listing_id=listing_id,
                images_count=len(listing.etsy_image_ids or []),
                has_zip=bool(listing.etsy_file_id),
            )

        return listing

    except Exception as exc:
        logger.exception("etsy_draft_dispatch_failed", workflow_id=str(workflow_id), error=str(exc))
        try:
            await uow.listing_drafts.update_etsy_dispatch_status(
                listing.id,
                status="failed",
                failure_reason=str(exc),
                last_synced_at=datetime.now(UTC),
            )
            await uow.audit.record(
                action=AuditAction.ETSY_DRAFT_FAILED,
                entity_type="ListingDraft",
                entity_id=listing.id,
                workflow_id=workflow_id,
                actor=str(owner_id),
                summary="Etsy draft creation failed.",
                metadata={"error": str(exc)},
            )
            await uow.commit()
        except Exception:
            pass
        raise


async def send_etsy_draft_created_notification(
    uow: UnitOfWork,
    telegram_gateway: TelegramGateway,
    owner_id: uuid.UUID,
    workflow_id: uuid.UUID,
    title: str,
    shop_name: str,
    listing_id: str,
    images_count: int,
    has_zip: bool,
) -> None:
    """Send structured completion notification with link to Etsy Shop Manager (ZERO publish action)."""
    manager_url = build_etsy_shop_manager_url(listing_id)

    msg_lines = [
        "<b>📦 Etsy Draft Created ✅</b>",
        "",
        f"<b>Shop:</b> {escape_html(shop_name)}",
        f"<b>Listing ID:</b> <code>{listing_id}</code>",
        f"<b>Title:</b> {escape_html(title)}",
        f"<b>Images:</b> {images_count} preview mockups uploaded",
        f"<b>Digital Package:</b> {'Attached ✅' if has_zip else 'Pending'}",
        "",
        "<i>This listing is in <b>draft</b> state. Publish manually inside Etsy Shop Manager when ready.</i>",
    ]

    inline_keyboard = [
        [{"text": "🛒 Open in Etsy Shop Manager", "url": manager_url}]
    ]

    await send_telegram_notification(
        uow=uow,
        telegram_gateway=telegram_gateway,
        owner_id=owner_id,
        text="\n".join(msg_lines),
        reply_markup={"inline_keyboard": inline_keyboard},
    )
