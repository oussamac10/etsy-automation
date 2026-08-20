"""Post-dispatch Etsy Draft Verification application service.

Fetches authoritative Etsy OpenAPI v3 listing state (listing, inventory, images, files, properties)
and compares it with expected local listing draft state to produce a structured verification report.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
import uuid
import structlog

from app.application.etsy_auth import get_valid_access_token
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.domain.errors import DomainError, EntityNotFoundError
from app.domain.etsy_verification import (
    EtsyDraftVerification,
    EtsyOverallVerificationStatus,
    EtsyVerificationCheck,
    EtsyVerificationCheckStatus,
    EtsyVerificationSummary,
    compare_etsy_draft,
)
from app.domain.production_resolver import filter_active_user_mockups
from app.infrastructure.security import CredentialCipher
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import EtsyGateway, ObjectStorage

logger = structlog.get_logger(__name__)


async def verify_etsy_draft_listing(
    workflow_id: uuid.UUID,
    owner_id: uuid.UUID,
    uow: UnitOfWork,
    cipher: CredentialCipher,
    etsy_gateway: EtsyGateway,
    storage: ObjectStorage | None = None,
) -> EtsyDraftVerification:
    """Fetch live Etsy listing data and verify against local ListingDraft expectation."""
    now = datetime.now(UTC)

    # 1. Load Workflow & Listing
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)
    if workflow.owner_id != owner_id:
        raise DomainError("Permission denied: You do not own this workflow.")

    listing = await uow.listing_drafts.get_by_workflow(workflow_id)
    if listing is None:
        raise EntityNotFoundError("ListingDraft", workflow_id)

    listing_id = getattr(listing, "etsy_listing_id", None)
    if not listing_id:
        # Listing draft has not been dispatched to Etsy yet
        summary = EtsyVerificationSummary(warnings=1, total=1)
        return EtsyDraftVerification(
            workflow_id=str(workflow_id),
            listing_id=None,
            status=EtsyOverallVerificationStatus.NEEDS_ATTENTION,
            verified_at=now,
            summary=summary,
            checks=[
                EtsyVerificationCheck(
                    key="not_dispatched",
                    label="Etsy Draft Status",
                    category="listing",
                    status=EtsyVerificationCheckStatus.MISSING,
                    expected="Draft dispatched to Etsy",
                    actual="Not dispatched",
                    message="Listing draft has not been created on Etsy yet. Click 'Create Etsy Draft' first.",
                    source="etsy_api",
                )
            ],
            error_message="Listing draft has not been created on Etsy yet.",
        )

    # 2. Check Shop Connection & Decrypt Token
    conn = await uow.shop_connections.get_by_user_id(owner_id)
    shop_id = getattr(conn, "etsy_shop_id", None) or getattr(conn, "shop_id", None)
    if conn is None or not conn.is_connected or not shop_id:
        summary = EtsyVerificationSummary(errors=1, total=1)
        report = EtsyDraftVerification(
            workflow_id=str(workflow_id),
            listing_id=str(listing_id),
            status=EtsyOverallVerificationStatus.FAILED,
            verified_at=now,
            summary=summary,
            checks=[
                EtsyVerificationCheck(
                    key="etsy_auth",
                    label="Etsy Connection",
                    category="listing",
                    status=EtsyVerificationCheckStatus.FAILED,
                    expected="Connected Etsy Shop",
                    actual="Disconnected",
                    message="No connected Etsy shop. Please connect your shop in Settings.",
                    source="etsy_api",
                )
            ],
            error_message="No connected Etsy shop. Reconnect your Etsy shop in Settings.",
        )
        return report

    try:
        access_token = await get_valid_access_token(
            uow=uow,
            cipher=cipher,
            etsy_gateway=etsy_gateway,
            owner_id=owner_id,
        )
    except Exception as exc:
        logger.error("etsy_verification_auth_failed", workflow_id=str(workflow_id), error=str(exc))
        summary = EtsyVerificationSummary(errors=1, total=1)
        report = EtsyDraftVerification(
            workflow_id=str(workflow_id),
            listing_id=str(listing_id),
            status=EtsyOverallVerificationStatus.FAILED,
            verified_at=now,
            summary=summary,
            checks=[
                EtsyVerificationCheck(
                    key="etsy_auth",
                    label="Etsy Authorization",
                    category="listing",
                    status=EtsyVerificationCheckStatus.FAILED,
                    expected="Valid OAuth Token",
                    actual="Expired / Revoked",
                    message=f"Etsy authorization failed: {exc}. Please reconnect your shop in Settings.",
                    source="etsy_api",
                )
            ],
            error_message="Etsy authorization failed. Please reconnect your Etsy shop in Settings.",
        )
        return report

    # 3. Concurrently Fetch Remote Etsy Resources
    fetch_tasks = [
        etsy_gateway.get_listing_details(access_token=access_token, shop_id=shop_id, listing_id=listing_id),
        etsy_gateway.get_listing_inventory(access_token=access_token, listing_id=listing_id),
        etsy_gateway.get_listing_images(access_token=access_token, listing_id=listing_id),
        etsy_gateway.get_listing_files(access_token=access_token, shop_id=shop_id, listing_id=listing_id),
        etsy_gateway.get_listing_properties(access_token=access_token, shop_id=shop_id, listing_id=listing_id),
    ]

    results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    raw_listing = results[0] if not isinstance(results[0], Exception) else None
    raw_inventory = results[1] if not isinstance(results[1], Exception) else None
    raw_images = results[2] if not isinstance(results[2], Exception) else []
    raw_files = results[3] if not isinstance(results[3], Exception) else []
    raw_properties = results[4] if not isinstance(results[4], Exception) else []

    # Handle 404 / remote draft deleted
    if raw_listing is None and (isinstance(results[0], ProviderError) and results[0].kind == ProviderErrorKind.NOT_FOUND or results[0] is None):
        logger.info("etsy_draft_not_found_on_remote", workflow_id=str(workflow_id), listing_id=listing_id)
        from app.application.etsy_draft import reconcile_etsy_draft
        await reconcile_etsy_draft(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            cipher=cipher,
            etsy_gateway=etsy_gateway,
        )
        summary = EtsyVerificationSummary(errors=1, total=1)
        report = EtsyDraftVerification(
            workflow_id=str(workflow_id),
            listing_id=str(listing_id),
            status=EtsyOverallVerificationStatus.FAILED,
            verified_at=now,
            summary=summary,
            checks=[
                EtsyVerificationCheck(
                    key="deleted_draft",
                    label="Etsy Listing Exists",
                    category="listing",
                    status=EtsyVerificationCheckStatus.MISSING,
                    expected=f"Listing #{listing_id}",
                    actual="Not found (404) on Etsy",
                    message="Draft was deleted or removed in Etsy Shop Manager. Workflow has been reset to Ready for Dispatch.",
                    source="etsy_api",
                )
            ],
            error_message="Etsy draft was deleted or not found on Etsy (404). Workflow reset to Ready for Dispatch.",
        )
        return report

    # 4. Resolve Expected Artifacts
    assets = await uow.assets.list_for_workflow(workflow_id)
    active_mockups = filter_active_user_mockups(assets)
    # Expected mockup count matches dispatched images or active mockups (or 1 master fallback)
    if listing.etsy_image_ids:
        expected_mockup_count = len(listing.etsy_image_ids)
    elif active_mockups:
        expected_mockup_count = len(active_mockups)
    else:
        expected_mockup_count = 1

    file_ids = list(listing.etsy_file_ids or ([listing.etsy_file_id] if listing.etsy_file_id else []))
    expected_file_count = max(len(file_ids), 1)

    expected_filenames = []
    for a in assets:
        if a.mime_type == "application/zip" or getattr(a, "provenance", {}).get("kind") == "customer_package":
            expected_filenames.append(a.storage_key.split("/")[-1])
    if not expected_filenames:
        clean_title = (listing.title or "package").replace(" ", "_")[:50]
        expected_filenames.append(f"{clean_title}.zip")

    # Serialize images & files to plain dicts for pure comparison
    images_dicts = [
        {"listing_image_id": getattr(img, "listing_image_id", str(img)), "rank": getattr(img, "rank", 1)}
        for img in (raw_images or [])
    ]
    files_dicts = [
        {
            "listing_file_id": getattr(f, "listing_file_id", str(f)),
            "filename": getattr(f, "filename", ""),
            "filesize": getattr(f, "filesize", None),
            "rank": getattr(f, "rank", 1),
        }
        for f in (raw_files or [])
    ]

    # 5. Run Pure Domain Comparison
    verification = compare_etsy_draft(
        workflow_id=str(workflow_id),
        listing_id=str(listing_id),
        expected_title=listing.title or "",
        expected_description=listing.description or "",
        expected_tags=list(listing.tags or []),
        expected_price_minor=listing.price_minor_units,
        expected_currency=listing.currency or "USD",
        expected_quantity=listing.quantity or 999,
        expected_sku=listing.sku,
        expected_taxonomy_id=listing.taxonomy_id,
        expected_taxonomy_path=listing.taxonomy_path,
        expected_shop_section_id=listing.shop_section_id,
        expected_shop_section_name=listing.shop_section_name,
        expected_should_auto_renew=listing.should_auto_renew,
        expected_properties=dict(listing.etsy_properties or {}),
        expected_mockup_count=expected_mockup_count,
        expected_file_count=expected_file_count,
        expected_filenames=expected_filenames,
        expected_ai_disclosure=listing.ai_disclosure,
        expected_shopping_cart_summary=listing.shopping_cart_summary,
        actual_listing=raw_listing if isinstance(raw_listing, dict) else None,
        actual_inventory=raw_inventory if isinstance(raw_inventory, dict) else None,
        actual_images=images_dicts,
        actual_files=files_dicts,
        actual_properties=raw_properties if isinstance(raw_properties, list) else [],
    )

    # 6. Persist Verification Snapshot on ListingDraft
    await uow.listing_drafts.update_etsy_verification(
        listing.id,
        status=verification.status.value,
        verified_at=verification.verified_at,
        result=verification.to_dict(),
    )

    # 7. Record Audit Trail
    await uow.audit.record(
        action=AuditAction.ETSY_DRAFT_VERIFIED,
        entity_type="listing_draft",
        entity_id=listing.id,
        workflow_id=workflow_id,
        actor=str(owner_id),
        summary=f"Etsy draft verified ({verification.status.value}): {verification.summary.synced} synced, {verification.summary.warnings} warnings, {verification.summary.manual_review} manual checks.",
        metadata={
            "workflow_id": str(workflow_id),
            "listing_id": str(listing_id),
            "status": verification.status.value,
            "synced": verification.summary.synced,
            "warnings": verification.summary.warnings,
            "errors": verification.summary.errors,
            "manual_review": verification.summary.manual_review,
        },
    )

    await uow.commit()

    return verification
