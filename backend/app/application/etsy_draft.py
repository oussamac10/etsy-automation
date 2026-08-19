"""Etsy draft creation and asset dispatch application service.

Guarantees:
- CRITICAL SAFETY: Strictly forces draft state (`state="draft"`). Zero publish or activation capability.
- Full Idempotency: Reconciles existing Etsy listings and uploaded assets across worker retries and partial failures.
- Deterministic asset ordering: Primary mockup -> additional mockups -> customer digital deliverables.
- Real Product Delivery: Never uses expiring external link PDFs. Uploads real buyer deliverables directly to Etsy (up to 5 digital files).
- Deterministic Seller Taxonomy: Resolves official Etsy digital category; no hardcoded physical fallbacks.
- State Machine integration: Transitions workflow from `READY_FOR_ETSY_DRAFT` to `ETSY_DRAFT_CREATED`.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
import structlog

from app.application.brand_resolver import resolve_connected_shop_name
from app.application.etsy_auth import get_valid_access_token
from app.application.package import CustomerPackageService
from app.application.telegram import send_telegram_notification
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.domain.errors import DomainError, EntityNotFoundError
from app.domain.etsy_delivery_planner import (
    EtsyDeliveryFile,
    EtsyDigitalDeliveryPlanner,
    MAX_ETSY_DIGITAL_FILES_COUNT,
)
from app.domain.media_selector import order_listing_mockup_assets
from app.domain.package_builder import (
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
    optimize_png_deflate,
)
from app.domain.production_resolver import (
    filter_active_user_mockups,
    get_production_master_asset,
)
from app.domain.tags import validate_listing_title, validate_tags
from app.domain.taxonomy_resolver import EtsyTaxonomyResolver
from app.domain.workflow import RunStatus
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
    ShopConnection,
)
from app.infrastructure.security import CredentialCipher
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import (
    EtsyGateway,
    EtsyListingDraftInput,
    ObjectStorage,
)
from app.ports.telegram import TelegramGateway
from app.providers.telegram import escape_html

logger = structlog.get_logger(__name__)

# Etsy Open API v3 maximum allowed bytes per uploaded digital file (20MB)
MAX_ETSY_DIGITAL_FILE_BYTES = 20 * 1024 * 1024


def build_etsy_shop_manager_url(listing_id: str) -> str:
    """Generate safe official Etsy Shop Manager listing editor URL."""
    return f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}"


async def validate_pre_dispatch(
    workflow_id: uuid.UUID,
    owner_id: uuid.UUID,
    uow: UnitOfWork,
    storage: ObjectStorage,
    etsy_gateway: EtsyGateway,
) -> tuple[ProductWorkflow, ListingDraft, ShopConnection, Asset, Asset]:
    """Validate all requirements before creating an Etsy draft listing.

    Validates:
    - Workflow ownership & state (`READY_FOR_ETSY_DRAFT`)
    - Active Etsy shop connection
    - Listing draft title, description, and exactly 13 tags
    - Production master PNG asset existence
    - Etsy seller taxonomy category resolution
    - Customer download delivery ZIP package existence (or builds it without mockups)
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

    # Validate Price
    if listing.price_minor_units is None or listing.price_minor_units <= 0:
        raise DomainError("Etsy listing price must be configured and greater than zero before dispatch.")

    # Validate / Resolve Master PNG
    master_asset = await get_production_master_asset(uow, workflow_id)
    if master_asset is None:
        raise DomainError("Master print-ready PNG asset is missing. Complete asset production before dispatching to Etsy.")

    # Validate / Resolve Taxonomy Category
    if not listing.taxonomy_id:
        try:
            taxonomy_nodes = await etsy_gateway.get_seller_taxonomy_nodes()
        except Exception as exc:
            logger.warning("failed_to_fetch_taxonomy_nodes", error=str(exc))
            taxonomy_nodes = []

        resolver = EtsyTaxonomyResolver()
        resolution = resolver.resolve(
            title=listing.title,
            tags=listing.tags,
            nodes=taxonomy_nodes,
        )
        listing = await uow.listing_drafts.update(
            listing.id,
            taxonomy_id=resolution.taxonomy_id,
            taxonomy_path=resolution.taxonomy_path,
        )
        await uow.commit()

    if not listing.taxonomy_id:
        raise DomainError("Could not resolve a valid Etsy seller taxonomy category for digital artwork.")

    # Validate / Build Etsy Delivery Package (without marketing mockups)
    package_service = CustomerPackageService(storage)
    zip_asset = await package_service.build_etsy_delivery_package(workflow_id, uow)

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
    """Orchestrate idempotent draft listing creation and real asset upload to Etsy Open API v3."""
    workflow, listing, conn, master_asset, zip_asset = await validate_pre_dispatch(
        workflow_id=workflow_id,
        owner_id=owner_id,
        uow=uow,
        storage=storage,
        etsy_gateway=etsy_gateway,
    )

    # Get decrypted OAuth access token (auto-refreshes if within buffer)
    access_token = await get_valid_access_token(
        uow=uow,
        cipher=cipher,
        etsy_gateway=etsy_gateway,
        owner_id=owner_id,
    )

    try:
        raw_price = getattr(listing, "price_minor_units", None)
        price_cents = raw_price if isinstance(raw_price, int) and raw_price > 0 else 499

        raw_qty = getattr(listing, "quantity", None)
        quantity = raw_qty if isinstance(raw_qty, int) and raw_qty > 0 else 999

        raw_sku = getattr(listing, "sku", None)
        sku = raw_sku if isinstance(raw_sku, str) and raw_sku.strip() else None

        raw_sec_id = getattr(listing, "shop_section_id", None)
        shop_section_id = raw_sec_id if isinstance(raw_sec_id, str) and raw_sec_id.strip() else None

        raw_renew = getattr(listing, "should_auto_renew", False)
        should_auto_renew = raw_renew if isinstance(raw_renew, bool) else False

        # Step 1: Create Etsy Draft Listing (Idempotent)
        listing_id = listing.etsy_listing_id
        if not listing_id:
            await uow.listing_drafts.update_etsy_dispatch_status(
                listing.id, status="creating_listing"
            )
            await uow.commit()

            if not listing.taxonomy_id:
                raise DomainError("A valid Etsy seller taxonomy category ID is required.")

            payload = EtsyListingDraftInput(
                title=listing.title,
                description=listing.description,
                tags=list(listing.tags),
                price_cents=price_cents,
                currency=listing.currency or "USD",
                taxonomy_id=listing.taxonomy_id,
                who_made="i_did",
                when_made="2020_2026",
                item_type="download",
                is_supply=False,
                quantity=quantity,
                sku=sku,
                shop_section_id=shop_section_id,
                should_auto_renew=should_auto_renew,
            )

            create_resp = await etsy_gateway.create_draft_listing(
                access_token=access_token,
                shop_id=conn.etsy_shop_id,
                listing=payload,
                idempotency_key=f"{workflow_id}_{listing.version}_{uuid.uuid4().hex[:8]}",
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
                taxonomy_id=listing.taxonomy_id,
                taxonomy_path=listing.taxonomy_path,
                sku=sku,
                shop_section_id=shop_section_id,
            )

        # Step 2: Upload Preview Images in Deterministic Order (Primary Mockup at Rank 1)
        await uow.listing_drafts.update_etsy_dispatch_status(
            listing.id, status="uploading_images"
        )
        await uow.commit()

        assets = await uow.assets.list_for_workflow(workflow_id)
        mockups = filter_active_user_mockups(assets, master_asset.id)
        raw_prim = getattr(listing, "primary_mockup_asset_id", None)
        prim_mockup_id = raw_prim if isinstance(raw_prim, uuid.UUID) else None
        preview_assets = order_listing_mockup_assets(
            mockups=mockups,
            master_asset=master_asset,
            primary_mockup_asset_id=prim_mockup_id,
            max_images=10,
        )

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

        # Step 3: Plan & Upload Real Customer Digital Download Files (Up to 5 files, <= 20MB each)
        await uow.listing_drafts.update_etsy_dispatch_status(
            listing.id, status="uploading_file"
        )
        await uow.commit()

        # Resolve dynamic connected Etsy shop name
        shop_name = await resolve_connected_shop_name(uow, workflow.owner_id)
        master_bytes = await storage.get(master_asset.storage_key)

        planner = EtsyDigitalDeliveryPlanner(
            max_file_bytes=MAX_ETSY_DIGITAL_FILE_BYTES,
            max_files_count=MAX_ETSY_DIGITAL_FILES_COUNT,
        )
        planned_files = planner.plan_delivery(
            master_png_bytes=master_bytes,
            listing_title=listing.title,
            shop_name=shop_name,
            master_width=master_asset.width or 4500,
            master_height=master_asset.height or 5400,
            include_pdf=True,
        )

        logger.info(
            "etsy_digital_delivery_planned",
            workflow_id=str(workflow_id),
            file_count=len(planned_files),
            filenames=[f.filename for f in planned_files],
            sizes=[len(f.content) for f in planned_files],
        )

        # Idempotent upload loop across all planned deliverables
        current_file_ids = list(
            listing.etsy_file_ids or ([listing.etsy_file_id] if listing.etsy_file_id else [])
        )

        for rank, delivery_file in enumerate(planned_files, start=1):
            if len(current_file_ids) >= rank:
                continue

            file_resp = await etsy_gateway.upload_listing_file(
                access_token=access_token,
                shop_id=conn.etsy_shop_id,
                listing_id=listing_id,
                file_bytes=delivery_file.content,
                filename=delivery_file.filename,
                rank=rank,
            )
            listing = await uow.listing_drafts.record_etsy_file_upload(
                listing.id, file_id=file_resp.listing_file_id
            )
            current_file_ids.append(file_resp.listing_file_id)
            await uow.commit()
            logger.info(
                "etsy_digital_file_uploaded",
                workflow_id=str(workflow_id),
                listing_id=listing_id,
                file_id=file_resp.listing_file_id,
                filename=delivery_file.filename,
                file_key=delivery_file.file_key,
                rank=rank,
            )

        if not current_file_ids:
            raise DomainError("No digital product files were uploaded to Etsy.")

        # Step 4: Update Listing Inventory SKU (if configured)
        active_sku = sku or (listing.sku if isinstance(getattr(listing, "sku", None), str) else None)
        if active_sku:
            try:
                await etsy_gateway.update_listing_inventory(
                    access_token=access_token,
                    listing_id=listing_id,
                    sku=active_sku,
                    price_cents=price_cents,
                    quantity=quantity,
                )
                logger.info(
                    "etsy_listing_inventory_updated",
                    workflow_id=str(workflow_id),
                    listing_id=listing_id,
                    sku=active_sku,
                )
            except Exception as exc:
                logger.warning(
                    "etsy_listing_inventory_update_skipped",
                    workflow_id=str(workflow_id),
                    listing_id=listing_id,
                    error=str(exc),
                )

        # Step 5: Update Taxonomy Properties/Attributes (if configured)
        raw_props = getattr(listing, "etsy_properties", None)
        active_props = raw_props if isinstance(raw_props, dict) else {}
        if active_props:
            for prop_id_str, prop_data in active_props.items():
                if isinstance(prop_data, dict):
                    pid = prop_data.get("property_id") or int(prop_id_str)
                    v_ids = prop_data.get("value_ids")
                    v_names = prop_data.get("values")
                    try:
                        await etsy_gateway.update_listing_property(
                            access_token=access_token,
                            shop_id=conn.etsy_shop_id,
                            listing_id=listing_id,
                            property_id=int(pid),
                            value_ids=v_ids,
                            values=v_names,
                        )
                        logger.info(
                            "etsy_listing_property_updated",
                            workflow_id=str(workflow_id),
                            listing_id=listing_id,
                            property_id=pid,
                        )
                    except Exception as exc:
                        logger.warning(
                            "etsy_listing_property_update_skipped",
                            workflow_id=str(workflow_id),
                            listing_id=listing_id,
                            property_id=pid,
                            error=str(exc),
                        )

        # Step 6: Finalize Workflow & Audit
        now = datetime.now(UTC)
        if workflow.state == RunStatus.READY_FOR_ETSY_DRAFT:
            await uow.workflows.transition(
                workflow,
                to_state=RunStatus.ETSY_DRAFT_CREATED,
                expected_version=workflow.version,
                reason="Etsy draft listing created successfully with mockups and real digital deliverables.",
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
                "taxonomy_id": listing.taxonomy_id,
                "taxonomy_path": listing.taxonomy_path,
                "image_count": len(listing.etsy_image_ids or []),
                "file_count": len(listing.etsy_file_ids or ([listing.etsy_file_id] if listing.etsy_file_id else [])),
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
                listing_id=listing_id,
                listing_title=listing.title,
                shop_name=conn.etsy_shop_name or "Etsy Shop",
                web_dashboard_url=web_dashboard_url,
            )

        logger.info(
            "etsy_draft_pipeline_completed",
            workflow_id=str(workflow_id),
            listing_id=listing_id,
            taxonomy_id=listing.taxonomy_id,
            taxonomy_path=listing.taxonomy_path,
            image_count=len(listing.etsy_image_ids or []),
            file_count=len(listing.etsy_file_ids or []),
        )
        return listing

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "etsy_draft_pipeline_failed",
            workflow_id=str(workflow_id),
            error=error_msg,
            exc_info=True,
        )
        try:
            listing = await uow.listing_drafts.update_etsy_dispatch_status(
                listing.id,
                status="failed",
                failure_reason=error_msg,
                last_synced_at=datetime.now(UTC),
            )
            await uow.commit()
        except Exception:
            logger.warning("failed_to_persist_etsy_draft_error", workflow_id=str(workflow_id))

        if telegram_gateway is not None:
            await send_etsy_draft_failed_notification(
                uow=uow,
                telegram_gateway=telegram_gateway,
                owner_id=owner_id,
                workflow_id=workflow_id,
                listing_title=listing.title if listing else "Listing",
                error_message=error_msg,
                web_dashboard_url=web_dashboard_url,
            )
        raise


async def send_etsy_draft_created_notification(
    uow: UnitOfWork,
    telegram_gateway: TelegramGateway,
    owner_id: uuid.UUID,
    workflow_id: uuid.UUID,
    listing_id: str,
    listing_title: str,
    shop_name: str,
    web_dashboard_url: str = "http://localhost:3000",
) -> None:
    """Send Telegram notification on successful Etsy draft listing creation."""
    try:
        etsy_edit_url = build_etsy_shop_manager_url(listing_id)
        app_url = f"{web_dashboard_url.rstrip('/')}/workflow/{workflow_id}?tab=listing"

        safe_title = escape_html(listing_title)
        safe_shop = escape_html(shop_name)

        text = (
            f"<b>Etsy Draft Created!</b>\n\n"
            f"Your listing draft for <b>{safe_title}</b> has been created on <b>{safe_shop}</b>.\n\n"
            f"<b>Listing ID:</b> <code>{listing_id}</code>\n"
            f"<b>State:</b> Draft (Private & Safe)\n\n"
            f"All mockups and digital download files have been attached.\n\n"
            f"<a href=\"{etsy_edit_url}\">Open in Etsy Shop Manager</a> | "
            f"<a href=\"{app_url}\">View in Dashboard</a>"
        )

        await send_telegram_notification(
            uow=uow,
            telegram_gateway=telegram_gateway,
            owner_id=owner_id,
            text=text,
        )
    except Exception as exc:
        logger.warning(
            "telegram_etsy_draft_created_notification_failed",
            owner_id=str(owner_id),
            workflow_id=str(workflow_id),
            error=str(exc),
        )


async def send_etsy_draft_failed_notification(
    uow: UnitOfWork,
    telegram_gateway: TelegramGateway,
    owner_id: uuid.UUID,
    workflow_id: uuid.UUID,
    listing_title: str,
    error_message: str,
    web_dashboard_url: str = "http://localhost:3000",
) -> None:
    """Send Telegram notification on Etsy draft creation failure."""
    try:
        app_url = f"{web_dashboard_url.rstrip('/')}/workflow/{workflow_id}?tab=listing"

        safe_title = escape_html(listing_title)
        safe_error = escape_html(error_message[:300])

        text = (
            f"<b>Etsy Dispatch Failed</b>\n\n"
            f"Draft creation for <b>{safe_title}</b> encountered an error:\n"
            f"<code>{safe_error}</code>\n\n"
            f"<a href=\"{app_url}\">Review & Retry in Dashboard</a>"
        )

        await send_telegram_notification(
            uow=uow,
            telegram_gateway=telegram_gateway,
            owner_id=owner_id,
            text=text,
        )
    except Exception as exc:
        logger.warning(
            "telegram_etsy_draft_failed_notification_failed",
            owner_id=str(owner_id),
            workflow_id=str(workflow_id),
            error=str(exc),
        )


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Outcome of reconciling a local workflow against remote Etsy draft state."""

    workflow_id: uuid.UUID
    reconciled: bool
    exists_on_etsy: bool
    status: str  # "synced", "draft_removed", "not_started", "reauth_required", "transient_error", "no_listing"
    etsy_listing_id: str | None = None
    detail: str | None = None


async def reconcile_etsy_draft(
    workflow_id: uuid.UUID,
    owner_id: uuid.UUID,
    uow: UnitOfWork,
    etsy_gateway: EtsyGateway,
    cipher: CredentialCipher | None = None,
    settings: Any = None,
) -> ReconciliationResult:
    """Reconcile local Etsy draft state against Etsy Open API v3.

    If the draft has been deleted/removed in Etsy Shop Manager, automatically resets
    the local Etsy draft metadata and transitions the workflow back to READY_FOR_ETSY_DRAFT
    so a new draft can be dispatched from the same approved campaign assets.
    """
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None or workflow.owner_id != owner_id:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)

    listing = await uow.listing_drafts.get_by_workflow(workflow_id)
    if listing is None or not listing.etsy_listing_id:
        return ReconciliationResult(
            workflow_id=workflow_id,
            reconciled=False,
            exists_on_etsy=False,
            status="no_listing",
            detail="No Etsy draft listing ID associated with this workflow.",
        )

    previous_listing_id = listing.etsy_listing_id
    shop_id = listing.etsy_shop_id or ""

    conn = await uow.shop_connections.get_by_user_id(owner_id)
    if conn is None or conn.connection_status == "disconnected" or not conn.is_connected:
        return ReconciliationResult(
            workflow_id=workflow_id,
            reconciled=False,
            exists_on_etsy=True,
            status="reauth_required",
            etsy_listing_id=previous_listing_id,
            detail="Etsy shop connection is disconnected or not authorized.",
        )

    if cipher is None:
        return ReconciliationResult(
            workflow_id=workflow_id,
            reconciled=False,
            exists_on_etsy=True,
            status="reauth_required",
            etsy_listing_id=previous_listing_id,
            detail="Server credential cipher is not configured.",
        )

    if not shop_id and conn.etsy_shop_id:
        shop_id = conn.etsy_shop_id

    # Retrieve valid access token
    try:
        access_token = await get_valid_access_token(
            uow=uow,
            cipher=cipher,
            etsy_gateway=etsy_gateway,
            owner_id=owner_id,
        )
    except Exception as exc:
        logger.warning(
            "reconcile_token_refresh_failed",
            workflow_id=str(workflow_id),
            error=str(exc),
        )
        return ReconciliationResult(
            workflow_id=workflow_id,
            reconciled=False,
            exists_on_etsy=True,
            status="reauth_required",
            etsy_listing_id=previous_listing_id,
            detail=f"Failed to obtain valid Etsy access token: {exc}",
        )

    # Check listing status on Etsy
    try:
        remote_listing = await etsy_gateway.get_listing(
            access_token=access_token,
            shop_id=shop_id,
            listing_id=previous_listing_id,
        )
    except ProviderError as pe:
        if pe.kind == ProviderErrorKind.NOT_FOUND:
            remote_listing = None
        elif pe.kind == ProviderErrorKind.AUTHENTICATION:
            logger.warning("reconcile_etsy_auth_failed", workflow_id=str(workflow_id), error=str(pe))
            return ReconciliationResult(
                workflow_id=workflow_id,
                reconciled=False,
                exists_on_etsy=True,
                status="reauth_required",
                etsy_listing_id=previous_listing_id,
                detail=f"Etsy authentication revoked: {pe.message}",
            )
        elif pe.is_retryable:
            logger.warning("reconcile_etsy_transient_error", workflow_id=str(workflow_id), error=str(pe))
            return ReconciliationResult(
                workflow_id=workflow_id,
                reconciled=False,
                exists_on_etsy=True,
                status="transient_error",
                etsy_listing_id=previous_listing_id,
                detail=f"Transient Etsy communication error: {pe.message}",
            )
        else:
            logger.warning("reconcile_etsy_request_error", workflow_id=str(workflow_id), error=str(pe))
            return ReconciliationResult(
                workflow_id=workflow_id,
                reconciled=False,
                exists_on_etsy=True,
                status="transient_error",
                etsy_listing_id=previous_listing_id,
                detail=f"Etsy API error: {pe.message}",
            )
    except Exception as exc:
        logger.warning("reconcile_unexpected_error", workflow_id=str(workflow_id), error=str(exc))
        return ReconciliationResult(
            workflow_id=workflow_id,
            reconciled=False,
            exists_on_etsy=True,
            status="transient_error",
            etsy_listing_id=previous_listing_id,
            detail=f"Unexpected error querying Etsy: {exc}",
        )

    now = datetime.now(UTC)

    # 1. Listing exists on Etsy
    if remote_listing is not None:
        listing.etsy_last_synced_at = now
        if remote_listing.state:
            listing.etsy_state = remote_listing.state
        await uow.commit()
        return ReconciliationResult(
            workflow_id=workflow_id,
            reconciled=True,
            exists_on_etsy=True,
            status="synced",
            etsy_listing_id=previous_listing_id,
            detail="Etsy draft listing verified and synchronized.",
        )

    # 2. Listing does NOT exist on Etsy (authoritative 404/deleted)
    logger.info(
        "etsy_draft_deleted_externally",
        workflow_id=str(workflow_id),
        previous_listing_id=previous_listing_id,
        shop_id=shop_id,
    )

    # Reset listing draft Etsy metadata (retains title, description, tags, taxonomy, IP findings, package assets)
    await uow.listing_drafts.clear_etsy_draft_state(listing.id, last_synced_at=now)

    # Transition workflow state back to READY_FOR_ETSY_DRAFT if currently ETSY_DRAFT_CREATED
    if workflow.state == RunStatus.ETSY_DRAFT_CREATED:
        await uow.workflows.transition(
            workflow,
            to_state=RunStatus.READY_FOR_ETSY_DRAFT,
            expected_version=workflow.version,
            reason="Etsy draft was deleted on Etsy. Reconciled local state back to ready for draft.",
            actor=str(owner_id),
        )

    # Record dedicated audit event
    await uow.audit.record(
        action=AuditAction.ETSY_DRAFT_REMOVED_EXTERNALLY,
        entity_type="ListingDraft",
        entity_id=listing.id,
        actor=str(owner_id),
        summary=f"Etsy draft listing {previous_listing_id} was removed in Etsy Shop Manager. Reset local state to ready for draft.",
        metadata={
            "workflow_id": str(workflow_id),
            "previous_etsy_listing_id": previous_listing_id,
            "shop_id": shop_id,
            "reason": "listing_not_found_on_etsy",
            "reconciled_at": now.isoformat(),
        },
    )

    await uow.commit()

    return ReconciliationResult(
        workflow_id=workflow_id,
        reconciled=True,
        exists_on_etsy=False,
        status="draft_removed",
        etsy_listing_id=None,
        detail="Draft listing no longer exists in Etsy Shop Manager. Campaign reset to ready for draft.",
    )
