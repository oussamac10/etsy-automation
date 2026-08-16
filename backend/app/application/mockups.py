"""Application service for custom mockup composition and template management."""

from __future__ import annotations

import base64
import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, cast

import httpx
from sqlalchemy.exc import IntegrityError

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import EntityNotFoundError, DomainError
from app.domain.mockup_products import get_product_preset, normalize_product_type
from app.domain.production_resolver import (
    filter_active_user_mockups,
    get_production_master_asset,
)
from app.infrastructure.mockup_template_store import MockupTemplateStore
from app.infrastructure.models.artwork import Asset
from app.infrastructure.security import validate_image_payload
from app.ports.providers import ObjectStorage
from app.providers.s3 import S3ObjectStorage


class MockupCompositionError(DomainError):
    """Raised when mockup composition or template resolution fails."""


@dataclass(frozen=True)
class CompositeMockupResult:
    mockup_url: str
    asset_id: uuid.UUID
    product_type: str
    template_id: str | None
    template_name: str
    is_cover: bool
    listing_order: int
    placement: dict[str, Any]
    width: int
    height: int


class MockupCompositionService:
    """Orchestrates custom user-template mockup composition."""

    def __init__(
        self,
        uow: UnitOfWork,
        storage: ObjectStorage,
        image_worker_url: str,
        image_max_input_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self.uow = uow
        self.storage = storage
        self.image_worker_url = image_worker_url.rstrip("/")
        self.image_max_input_bytes = image_max_input_bytes
        self.template_store = MockupTemplateStore(cast(S3ObjectStorage, storage))

    async def composite_custom_mockup(
        self,
        *,
        owner_id: uuid.UUID,
        workflow_id: uuid.UUID,
        product_type: str,
        template_id: str | None = None,
        template_name: str | None = None,
        template_image_base64: str | None = None,
        save_as_template: bool = False,
        placement: dict[str, Any] | None = None,
        is_cover: bool | None = None,
        target_asset_id: uuid.UUID | None = None,
        master_asset_id: uuid.UUID | None = None,
    ) -> CompositeMockupResult:
        """Composite workflow master PNG onto a custom template photo."""
        workflow = await self.uow.workflows.get(workflow_id)
        if not workflow or workflow.owner_id != owner_id:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        canonical_prod = normalize_product_type(product_type) or product_type
        preset = get_product_preset(canonical_prod)

        # 1. Authoritatively resolve master asset
        master_asset = await get_production_master_asset(
            self.uow,
            workflow_id=workflow_id,
            master_asset_id=master_asset_id,
        )
        if not master_asset:
            raise MockupCompositionError("No production master PNG available for this workflow.")

        master_bytes = await self.storage.get(master_asset.storage_key)

        # 2. Resolve template bytes & placement
        resolved_placement = placement or {
            "left_pct": preset.default_left_pct,
            "top_pct": preset.default_top_pct,
            "width_pct": preset.default_width_pct,
            "height_pct": preset.default_height_pct,
            "angle_deg": 0.0,
            "blend_mode": preset.default_blend_mode,
        }
        resolved_template_id = template_id
        resolved_template_name = template_name or f"{canonical_prod.replace('_', ' ').capitalize()} Mockup"
        resolved_template_storage_key: str | None = None
        template_bytes: bytes | None = None

        if template_image_base64:
            try:
                template_bytes = base64.b64decode(template_image_base64)
            except Exception as exc:
                raise MockupCompositionError(f"Invalid base64 encoded template image: {exc}") from exc

            validate_image_payload(
                template_bytes,
                "image/jpeg",
                max_bytes=self.image_max_input_bytes,
            )

            if save_as_template:
                saved_item = await self.template_store.save_template(
                    owner_id=owner_id,
                    name=resolved_template_name,
                    product_type=canonical_prod,
                    image_bytes=template_bytes,
                    content_type="image/jpeg",
                    placement=resolved_placement,
                )
                resolved_template_id = saved_item.id
                resolved_template_storage_key = saved_item.storage_key
            else:
                tpl_img_id = uuid.uuid4()
                raw_tpl_key = f"mockup-templates/{owner_id}/{canonical_prod}/source_{tpl_img_id}.jpg"
                await self.storage.put(raw_tpl_key, template_bytes, content_type="image/jpeg")
                resolved_template_storage_key = raw_tpl_key
                resolved_template_id = str(tpl_img_id)
        elif template_id:
            existing_template = await self.template_store.get_template(owner_id=owner_id, template_id=template_id)
            if not existing_template:
                raise MockupCompositionError("Selected template not found.")
            template_bytes = await self.storage.get(existing_template.storage_key)
            resolved_template_storage_key = existing_template.storage_key
            resolved_template_name = template_name or existing_template.name
            if not placement:
                resolved_placement = {
                    "left_pct": existing_template.placement.left_pct,
                    "top_pct": existing_template.placement.top_pct,
                    "width_pct": existing_template.placement.width_pct,
                    "height_pct": existing_template.placement.height_pct,
                    "angle_deg": existing_template.placement.angle_deg,
                    "blend_mode": existing_template.placement.blend_mode,
                }
        else:
            raise MockupCompositionError("Either template_image_base64 or template_id must be provided.")

        if not template_bytes:
            raise MockupCompositionError("Failed to read template image.")

        # 3. Call image-worker microservice
        worker_payload = {
            "artwork_base64": base64.b64encode(master_bytes).decode("utf-8"),
            "template_base64": base64.b64encode(template_bytes).decode("utf-8"),
            "placement": resolved_placement,
            "format": "jpeg",
            "quality": 92,
        }

        async with httpx.AsyncClient(timeout=45.0) as http_client:
            resp = await http_client.post(f"{self.image_worker_url}/pipeline/custom-mockup", json=worker_payload)
            if resp.status_code != 200:
                raise MockupCompositionError(
                    f"Image worker failed to composite custom mockup: {resp.text[:200]}"
                )
            result_data = resp.json()

        composited_bytes = base64.b64decode(result_data["mockup_base64"])
        out_w = result_data.get("width", 1200)
        out_h = result_data.get("height", 1200)

        # 4. Target asset resolution and listing order / cover calculation
        all_wf_assets = await self.uow.assets.list_for_workflow(workflow_id)
        existing_mockups = filter_active_user_mockups(all_wf_assets)

        target_asset: Asset | None = None
        if target_asset_id:
            target_asset = next((a for a in existing_mockups if a.id == target_asset_id), None)

        if target_asset and target_asset.provenance:
            order = int(str(target_asset.provenance.get("listing_order", "1") or "1"))
            resolved_is_cover = bool(target_asset.provenance.get("is_cover", False))
            if is_cover is not None:
                resolved_is_cover = is_cover
        else:
            existing_orders = [
                int(str(m.provenance.get("listing_order", "0") or "0"))
                for m in existing_mockups
                if m.provenance
            ]
            order = (max(existing_orders) + 1) if existing_orders else 1
            resolved_is_cover = True if len(existing_mockups) == 0 else bool(is_cover)

        if resolved_is_cover:
            for other in existing_mockups:
                if target_asset and other.id == target_asset.id:
                    continue
                if other.provenance and other.provenance.get("is_cover"):
                    other.provenance = dict(other.provenance, is_cover=False)
                    await self.uow.session.flush()

        mock_sha256 = hashlib.sha256(composited_bytes).hexdigest()

        mockup_id = target_asset.id if target_asset else uuid.uuid4()
        mockup_storage_key = f"production/{workflow_id}/mockups/custom_{canonical_prod}_{mockup_id}.jpg"
        await self.storage.put(mockup_storage_key, composited_bytes, content_type="image/jpeg")
        mockup_url = await self.storage.signed_url(mockup_storage_key, expires_in_seconds=86400 * 7)

        provenance_data: dict[str, Any] = {
            "phase": 7,
            "asset_type": "mockup",
            "source": "user_template",
            "product_type": canonical_prod,
            "template_id": resolved_template_id,
            "template_name": resolved_template_name,
            "template_storage_key": resolved_template_storage_key,
            "source_asset_id": str(master_asset.id),
            "placement": resolved_placement,
            "is_cover": resolved_is_cover,
            "listing_order": order,
            "created_for_listing": True,
        }

        if target_asset:
            target_asset.storage_key = mockup_storage_key
            target_asset.mime_type = "image/jpeg"
            target_asset.byte_size = len(composited_bytes)
            target_asset.checksum_sha256 = mock_sha256
            target_asset.width = out_w
            target_asset.height = out_h
            target_asset.provenance = provenance_data
            await self.uow.session.flush()
        else:
            custom_asset = Asset(
                id=mockup_id,
                workflow_id=workflow_id,
                artwork_job_id=None,
                derived_from_id=master_asset.id,
                storage_key=mockup_storage_key,
                mime_type="image/jpeg",
                byte_size=len(composited_bytes),
                checksum_sha256=mock_sha256,
                width=out_w,
                height=out_h,
                has_alpha=False,
                has_transparent_pixels=False,
                quality_check={},
                provenance=provenance_data,
            )
            await self.uow.assets.add(custom_asset)

        try:
            await self.uow.session.commit()
        except IntegrityError:
            await self.uow.session.rollback()
            # Refetch and update existing asset on concurrent collision
            refreshed = await self.uow.assets.list_for_workflow(workflow_id)
            existing = next((a for a in refreshed if a.checksum_sha256 == mock_sha256), None)
            if existing:
                existing.storage_key = mockup_storage_key
                existing.mime_type = "image/jpeg"
                existing.byte_size = len(composited_bytes)
                existing.width = out_w
                existing.height = out_h
                existing.provenance = provenance_data
                await self.uow.session.commit()
                mockup_id = existing.id
            else:
                raise

        return CompositeMockupResult(
            mockup_url=mockup_url,
            asset_id=mockup_id,
            product_type=canonical_prod,
            template_id=resolved_template_id,
            template_name=resolved_template_name,
            is_cover=resolved_is_cover,
            listing_order=order,
            placement=resolved_placement,
            width=out_w,
            height=out_h,
        )
