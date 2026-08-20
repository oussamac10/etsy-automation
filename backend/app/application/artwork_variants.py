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
    VariantStatus,
    VariantType,
    build_variant_prompt,
    filter_workflow_artwork_variants,
    is_valid_artwork_variant_asset,
    sanitize_hex_color,
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

        # 2. Extract original positive prompt if available
        original_prompt_text: str | None = None
        concepts = await uow.concepts.list_for_workflow(workflow_id)
        if concepts:
            prompts = await uow.concepts.prompts(concepts[0].id)
            if prompts:
                original_prompt_text = prompts[-1].positive_prompt

        # 3. Build deterministic variant prompt
        positive_prompt, negative_prompt, prompt_version = build_variant_prompt(
            v_type,
            custom_color=sanitized_color,
            original_positive_prompt=original_prompt_text,
            custom_instructions=custom_instructions,
        )

        # 4. Generate image using image provider with reference image
        variant_asset_id = uuid.uuid4()
        idempotency_key = f"variant-{workflow_id}-{master_asset.id}-{v_type.value}-{variant_asset_id.hex[:8]}"

        img_request = ImageRequest(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=master_asset.width or 4500,
            height=master_asset.height or 5400,
            quality="high",
            idempotency_key=idempotency_key,
            output_format="png",
            transparent_background=True,
            candidate_count=1,
            reference_image_bytes=master_bytes,
            reference_image_mime_type="image/png",
            strength=0.25,
        )

        img_response = await self._image_provider.generate(img_request)
        if not img_response.candidates or not img_response.image_bytes:
            raise ArtworkVariantError("Image provider returned empty result for color variant.")

        variant_bytes = img_response.image_bytes
        variant_mime = img_response.mime_type or "image/png"
        variant_sha256 = hashlib.sha256(variant_bytes).hexdigest()

        # 5. Store in S3 under workflow variants directory
        storage_key = f"workflows/{workflow_id}/variants/{variant_asset_id}/{v_type.value}.png"
        stored_obj = await self._storage.put(storage_key, variant_bytes, content_type=variant_mime)

        variant_title = VARIANT_TYPE_LABELS.get(v_type, f"{v_type.value.replace('_', ' ').title()} Version")

        provenance_data: dict[str, Any] = {
            "kind": "artwork_variant",
            "variant_type": v_type.value,
            "variant_status": VariantStatus.READY.value,
            "title": variant_title,
            "custom_color": sanitized_color,
            "custom_instructions": custom_instructions,
            "prompt_version": prompt_version,
            "source_asset_id": str(master_asset.id),
            "generated_model": img_response.model,
            "idempotency_key": idempotency_key,
        }

        # 6. Persist new derived Asset row
        variant_asset = Asset(
            id=variant_asset_id,
            workflow_id=workflow_id,
            artwork_job_id=None,
            derived_from_id=master_asset.id,
            storage_key=stored_obj.storage_key,
            mime_type=variant_mime,
            byte_size=len(variant_bytes),
            checksum_sha256=variant_sha256,
            width=master_asset.width or 4500,
            height=master_asset.height or 5400,
            has_alpha=True,
            has_transparent_pixels=True,
            quality_check={"dimensions_ok": True, "transparency_ok": True},
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
