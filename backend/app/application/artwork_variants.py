"""Application service for generating, listing, approving, rejecting, and deleting artwork color variants."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import uuid
from typing import Any
import structlog

from app.application.unit_of_work import UnitOfWork
from app.domain.artwork_variants import (
    DEFAULT_PROMPT_VERSION,
    VARIANT_TYPE_LABELS,
    ArtworkVariantValidationError,
    VariantStatus,
    VariantType,
    filter_workflow_artwork_variants,
    is_valid_artwork_variant_asset,
    is_variant_outdated,
    recolor_artwork_variant,
    sanitize_hex_color,
    validate_artwork_variant,
)
from app.domain.errors import DomainError, EntityNotFoundError
from app.domain.production_resolver import get_production_master_asset
from app.infrastructure.models import Asset, ProductWorkflow
from app.ports.providers import ImageGenerationProvider, ImageRequest, ObjectStorage

logger = structlog.get_logger(__name__)


class ArtworkVariantError(DomainError):
    """Raised when artwork variant generation or operation fails."""


class ArtworkVariantService:
    """Coordinates deterministic creation, approval, and management of artwork color variants."""

    def __init__(
        self,
        storage: ObjectStorage,
        image_provider: ImageGenerationProvider,
    ) -> None:
        self._storage = storage
        self._image_provider = image_provider

    async def list_variants(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> list[Asset]:
        """List all derived color variants for a given workflow."""
        assets = await uow.assets.list_for_workflow(workflow_id)
        return filter_workflow_artwork_variants(assets)

    async def generate_variant(
        self,
        *,
        workflow_id: uuid.UUID,
        owner_id: uuid.UUID,
        variant_type: VariantType | str,
        custom_color: str | None = None,
        custom_instructions: str | None = None,
        uow: UnitOfWork,
    ) -> Asset:
        """Generate a high-contrast transparent PNG color variant derived from the approved master PNG."""
        workflow: ProductWorkflow | None = await uow.workflows.get(workflow_id)
        if workflow is None or workflow.owner_id != owner_id:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        # Normalize variant type
        v_type = VariantType(str(variant_type)) if not isinstance(variant_type, VariantType) else variant_type
        sanitized_color = sanitize_hex_color(custom_color) if v_type == VariantType.CUSTOM else None

        # 1. Authoritatively resolve master asset (never mutate source master)
        master_asset = await get_production_master_asset(uow, workflow_id)
        if master_asset is None:
            # Fallback to any non-mockup PNG asset
            all_assets = await uow.assets.list_for_workflow(workflow_id)
            master_asset = next(
                (
                    a
                    for a in all_assets
                    if a.mime_type == "image/png"
                    and "/mockups/" not in a.storage_key
                    and not a.storage_key.endswith(".zip")
                ),
                None,
            )

        if master_asset is None:
            raise ArtworkVariantError("No master PNG available to generate variants from.")

        logger.info(
            "generating_artwork_variant",
            workflow_id=str(workflow_id),
            master_id=str(master_asset.id),
            variant_type=v_type.value,
            custom_color=sanitized_color,
        )

        master_bytes = await self._storage.get(master_asset.storage_key)
        if not master_bytes:
            raise ArtworkVariantError("Failed to load master PNG bytes from storage.")

        # 2. Deterministic Pixel/Color-Range Recolor Engine (Exact Alpha & Composition Preserved)
        variant_asset_id = uuid.uuid4()
        idempotency_key = f"variant-{workflow_id}-{master_asset.id}-{v_type.value}-{variant_asset_id.hex[:8]}"

        try:
            variant_bytes, validation_report = recolor_artwork_variant(
                source_bytes=master_bytes,
                variant_type=v_type,
                target_color_hex=sanitized_color,
            )
        except ArtworkVariantValidationError as val_err:
            logger.error("artwork_variant_validation_failed", error=str(val_err), workflow_id=str(workflow_id))
            raise ArtworkVariantError(f"Validation failed: {val_err}") from val_err
        except Exception as exc:
            logger.error("artwork_variant_recolor_failed", error=str(exc), workflow_id=str(workflow_id))
            raise ArtworkVariantError(f"Failed to recolor artwork: {exc}") from exc

        variant_mime = "image/png"
        variant_sha256 = hashlib.sha256(variant_bytes).hexdigest()

        # 3. Store in S3 under workflow variants directory
        storage_key = f"workflows/{workflow_id}/variants/{variant_asset_id}/{v_type.value}.png"
        stored_obj = await self._storage.put(storage_key, variant_bytes, content_type=variant_mime)

        variant_title = VARIANT_TYPE_LABELS.get(v_type, f"{v_type.value.replace('_', ' ').title()} Version")

        provenance_data: dict[str, Any] = {
            "kind": "artwork_variant",
            "variant_type": v_type.value,
            "variant_status": VariantStatus.READY.value,
            "title": variant_title,
            "custom_color": sanitized_color or validation_report.get("target_color"),
            "custom_instructions": custom_instructions,
            "prompt_version": DEFAULT_PROMPT_VERSION,
            "source_asset_id": str(master_asset.id),
            "generated_model": "deterministic_recolor_engine_v2",
            "idempotency_key": idempotency_key,
            "validation_report": validation_report,
        }

        # 4. Persist new derived Asset row
        variant_asset = Asset(
            id=variant_asset_id,
            workflow_id=workflow_id,
            artwork_job_id=None,
            derived_from_id=master_asset.id,
            storage_key=stored_obj.storage_key,
            mime_type=variant_mime,
            byte_size=len(variant_bytes),
            checksum_sha256=variant_sha256,
            width=validation_report.get("width") or master_asset.width or 4500,
            height=validation_report.get("height") or master_asset.height or 5400,
            has_alpha=True,
            has_transparent_pixels=True,
            quality_check=validation_report,
            provenance=provenance_data,
        )
        await uow.assets.add(variant_asset)
        await uow.commit()

        logger.info(
            "artwork_variant_created",
            workflow_id=str(workflow_id),
            variant_id=str(variant_asset.id),
            variant_type=v_type.value,
            status=VariantStatus.READY.value,
        )
        return variant_asset

    async def approve_variant(
        self,
        *,
        workflow_id: uuid.UUID,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> Asset:
        """Explicitly approve a color variant for mockups and customer ZIP packages."""
        workflow = await uow.workflows.get(workflow_id)
        if workflow is None or workflow.owner_id != owner_id:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        asset = await uow.assets.get(asset_id)
        if asset is None or asset.workflow_id != workflow_id:
            raise EntityNotFoundError("Asset", asset_id)

        if not is_valid_artwork_variant_asset(asset.provenance):
            raise ArtworkVariantError("Target asset is not an artwork color variant.")

        updated_prov = dict(asset.provenance or {})
        updated_prov["variant_status"] = VariantStatus.APPROVED.value
        updated_prov["approved_at"] = datetime.now(UTC).isoformat()
        asset.provenance = updated_prov

        await uow.commit()
        logger.info("artwork_variant_approved", workflow_id=str(workflow_id), variant_id=str(asset.id))
        return asset

    async def reject_variant(
        self,
        *,
        workflow_id: uuid.UUID,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> Asset:
        """Reject a color variant."""
        workflow = await uow.workflows.get(workflow_id)
        if workflow is None or workflow.owner_id != owner_id:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        asset = await uow.assets.get(asset_id)
        if asset is None or asset.workflow_id != workflow_id:
            raise EntityNotFoundError("Asset", asset_id)

        if not is_valid_artwork_variant_asset(asset.provenance):
            raise ArtworkVariantError("Target asset is not an artwork color variant.")

        updated_prov = dict(asset.provenance or {})
        updated_prov["variant_status"] = VariantStatus.REJECTED.value
        updated_prov["rejected_at"] = datetime.now(UTC).isoformat()
        asset.provenance = updated_prov

        await uow.commit()
        logger.info("artwork_variant_rejected", workflow_id=str(workflow_id), variant_id=str(asset.id))
        return asset

    async def delete_variant(
        self,
        *,
        workflow_id: uuid.UUID,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> None:
        """Delete an artwork variant asset and remove its file from storage."""
        workflow = await uow.workflows.get(workflow_id)
        if workflow is None or workflow.owner_id != owner_id:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        asset = await uow.assets.get(asset_id)
        if asset is None or asset.workflow_id != workflow_id:
            raise EntityNotFoundError("Asset", asset_id)

        if not is_valid_artwork_variant_asset(asset.provenance):
            raise ArtworkVariantError("Target asset is not an artwork color variant.")

        storage_key = asset.storage_key
        await uow.assets.delete(asset)
        await uow.commit()

        try:
            await self._storage.delete(storage_key)
        except Exception as del_err:
            logger.warning("failed_deleting_variant_storage", storage_key=storage_key, error=str(del_err))

    async def update_variant_package_inclusion(
        self,
        *,
        workflow_id: uuid.UUID,
        asset_id: uuid.UUID,
        include_in_buyer_package: bool,
        owner_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> Asset:
        """Update whether an approved, current variant is included in the buyer deliverable ZIP package."""
        workflow = await uow.workflows.get(workflow_id)
        if workflow is None or workflow.owner_id != owner_id:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        asset = await uow.assets.get(asset_id)
        if asset is None or asset.workflow_id != workflow_id:
            raise EntityNotFoundError("Asset", asset_id)

        if not is_valid_artwork_variant_asset(asset.provenance):
            raise ArtworkVariantError("Target asset is not an artwork color variant.")

        updated_prov = dict(asset.provenance or {})

        # Validation Rule: Only approved variants can be included
        if include_in_buyer_package:
            if updated_prov.get("variant_status") != VariantStatus.APPROVED.value:
                raise ArtworkVariantError(
                    "Only approved variants can be included in the buyer package. Approve the variant first."
                )

            # Check if source master is current
            master_asset = await get_production_master_asset(uow, workflow_id)
            if is_variant_outdated(asset, master_asset):
                raise ArtworkVariantError(
                    "This variant was generated from an older master artwork. Regenerate before including it in the buyer package."
                )

        updated_prov["include_in_buyer_package"] = bool(include_in_buyer_package)
        updated_prov["buyer_package_updated_at"] = datetime.now(UTC).isoformat()
        asset.provenance = updated_prov

        await uow.commit()
        logger.info(
            "artwork_variant_package_inclusion_updated",
            workflow_id=str(workflow_id),
            variant_id=str(asset.id),
            include_in_buyer_package=include_in_buyer_package,
        )
        return asset

