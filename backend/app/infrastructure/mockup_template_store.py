"""Persistent Mockup Template Store backed by S3 / MinIO object storage.

Allows storing, retrieving, and reusing custom mockup templates per owner and product type
with exact placement coordinates and texture blend modes.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import structlog

from app.infrastructure.mockup_catalog import get_product_preset, normalize_mockup_product
from app.providers.s3 import S3ObjectStorage

logger = structlog.get_logger(__name__)


@dataclass
class CustomMockupPlacement:
    left_pct: float = 0.25
    top_pct: float = 0.25
    width_pct: float = 0.50
    height_pct: float = 0.50
    angle_deg: float = 0.0
    blend_mode: str = "multiply"  # "multiply" for realistic shadows/wrinkles, "over" for opaque


@dataclass
class MockupTemplateItem:
    id: str
    owner_id: str
    name: str
    product_type: str
    storage_key: str
    url: str
    placement: CustomMockupPlacement
    created_at: str
    is_custom: bool = True


class MockupTemplateStore:
    """Store and retrieve persistent custom mockup templates from S3 scoped per owner."""

    def __init__(self, storage: S3ObjectStorage) -> None:
        self._storage = storage

    async def list_templates(
        self,
        owner_id: uuid.UUID | str,
        product_type: str | None = None,
    ) -> list[MockupTemplateItem]:
        """List all saved mockup templates for an owner, optionally filtered by canonical product type."""
        owner_str = str(owner_id)
        canonical_target = normalize_mockup_product(product_type) if product_type else None
        if canonical_target:
            prefix = f"mockup-templates/{owner_str}/{canonical_target}/"
        else:
            prefix = f"mockup-templates/{owner_str}/"

        templates: list[MockupTemplateItem] = []
        try:
            client = self._storage._get_client()
            response = await asyncio.to_thread(
                client.list_objects_v2,
                Bucket=self._storage._bucket_name,
                Prefix=prefix,
            )
            contents = response.get("Contents", [])

            json_keys = [item["Key"] for item in contents if item["Key"].endswith(".json")]

            for json_key in json_keys:
                try:
                    data = await self._storage.get(json_key)
                    meta = json.loads(data.decode("utf-8"))

                    t_id = meta.get("id")
                    t_owner = meta.get("owner_id", owner_str)
                    t_name = meta.get("name", "Custom Mockup")
                    t_prod = meta.get("product_type", "tshirt")
                    t_img_key = meta.get("storage_key")
                    placement_data = meta.get("placement", {})
                    created_at = meta.get("created_at", datetime.now(timezone.utc).isoformat())

                    if not t_img_key:
                        continue

                    # Generate presigned URL for thumbnail / display
                    url = await self._storage.signed_url(t_img_key, expires_in_seconds=86400 * 7)

                    preset = get_product_preset(t_prod)
                    placement = CustomMockupPlacement(
                        left_pct=float(placement_data.get("left_pct", preset.default_left_pct)),
                        top_pct=float(placement_data.get("top_pct", preset.default_top_pct)),
                        width_pct=float(placement_data.get("width_pct", preset.default_width_pct)),
                        height_pct=float(placement_data.get("height_pct", preset.default_height_pct)),
                        angle_deg=float(placement_data.get("angle_deg", 0.0)),
                        blend_mode=str(placement_data.get("blend_mode", preset.default_blend_mode)),
                    )

                    templates.append(
                        MockupTemplateItem(
                            id=t_id,
                            owner_id=t_owner,
                            name=t_name,
                            product_type=t_prod,
                            storage_key=t_img_key,
                            url=url,
                            placement=placement,
                            created_at=created_at,
                            is_custom=True,
                        )
                    )
                except Exception as err:
                    logger.warning("failed_to_parse_mockup_template", key=json_key, error=str(err))

        except Exception as exc:
            logger.error("failed_to_list_mockup_templates", error=str(exc))

        # Sort newest first
        templates.sort(key=lambda t: t.created_at, reverse=True)
        return templates

    async def save_template(
        self,
        owner_id: uuid.UUID | str,
        name: str,
        product_type: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
        placement: CustomMockupPlacement | dict | None = None,
    ) -> MockupTemplateItem:
        """Save a new custom mockup template image and its manifest to S3 for an owner."""
        owner_str = str(owner_id)
        canonical = normalize_mockup_product(product_type) or "tshirt"
        template_id = str(uuid.uuid4())
        preset = get_product_preset(canonical)

        ext = "png" if "png" in content_type.lower() else ("webp" if "webp" in content_type.lower() else "jpg")
        image_key = f"mockup-templates/{owner_str}/{canonical}/{template_id}.{ext}"
        json_key = f"mockup-templates/{owner_str}/{canonical}/{template_id}.json"

        # 1. Upload template image
        await self._storage.put(image_key, image_bytes, content_type=content_type)

        # 2. Build placement object
        if isinstance(placement, dict):
            placement_obj = CustomMockupPlacement(
                left_pct=float(placement.get("left_pct", preset.default_left_pct)),
                top_pct=float(placement.get("top_pct", preset.default_top_pct)),
                width_pct=float(placement.get("width_pct", preset.default_width_pct)),
                height_pct=float(placement.get("height_pct", preset.default_height_pct)),
                angle_deg=float(placement.get("angle_deg", 0.0)),
                blend_mode=str(placement.get("blend_mode", preset.default_blend_mode)),
            )
        elif isinstance(placement, CustomMockupPlacement):
            placement_obj = placement
        else:
            placement_obj = CustomMockupPlacement(
                left_pct=preset.default_left_pct,
                top_pct=preset.default_top_pct,
                width_pct=preset.default_width_pct,
                height_pct=preset.default_height_pct,
                blend_mode=preset.default_blend_mode,
            )

        manifest = {
            "id": template_id,
            "owner_id": owner_str,
            "name": name.strip() or f"Custom {canonical.capitalize()} Mockup",
            "product_type": canonical,
            "storage_key": image_key,
            "placement": asdict(placement_obj),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # 3. Upload manifest JSON
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        await self._storage.put(json_key, manifest_bytes, content_type="application/json")

        url = await self._storage.signed_url(image_key, expires_in_seconds=86400 * 7)

        return MockupTemplateItem(
            id=template_id,
            owner_id=owner_str,
            name=manifest["name"],
            product_type=canonical,
            storage_key=image_key,
            url=url,
            placement=placement_obj,
            created_at=manifest["created_at"],
            is_custom=True,
        )

    async def get_template(
        self,
        owner_id: uuid.UUID | str,
        template_id: str,
    ) -> MockupTemplateItem | None:
        """Find and return a specific template by ID for an owner."""
        all_templates = await self.list_templates(owner_id)
        for t in all_templates:
            if t.id == template_id:
                return t
        return None

    async def update_template(
        self,
        owner_id: uuid.UUID | str,
        template_id: str,
        name: str | None = None,
        placement: CustomMockupPlacement | dict | None = None,
        product_type: str | None = None,
    ) -> MockupTemplateItem | None:
        """Update metadata, name, or placement coordinates of an existing template."""
        owner_str = str(owner_id)
        existing = await self.get_template(owner_id, template_id)
        if not existing:
            return None

        canonical = normalize_mockup_product(product_type) or existing.product_type
        json_key = f"mockup-templates/{owner_str}/{existing.product_type}/{template_id}.json"

        # Build updated placement
        if placement is not None:
            if isinstance(placement, dict):
                placement_obj = CustomMockupPlacement(
                    left_pct=float(placement.get("left_pct", existing.placement.left_pct)),
                    top_pct=float(placement.get("top_pct", existing.placement.top_pct)),
                    width_pct=float(placement.get("width_pct", existing.placement.width_pct)),
                    height_pct=float(placement.get("height_pct", existing.placement.height_pct)),
                    angle_deg=float(placement.get("angle_deg", existing.placement.angle_deg)),
                    blend_mode=str(placement.get("blend_mode", existing.placement.blend_mode)),
                )
            else:
                placement_obj = placement
        else:
            placement_obj = existing.placement

        updated_name = name.strip() if name and name.strip() else existing.name

        manifest = {
            "id": template_id,
            "owner_id": owner_str,
            "name": updated_name,
            "product_type": canonical,
            "storage_key": existing.storage_key,
            "placement": asdict(placement_obj),
            "created_at": existing.created_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        await self._storage.put(json_key, manifest_bytes, content_type="application/json")

        return MockupTemplateItem(
            id=template_id,
            owner_id=owner_str,
            name=updated_name,
            product_type=canonical,
            storage_key=existing.storage_key,
            url=existing.url,
            placement=placement_obj,
            created_at=existing.created_at,
            is_custom=True,
        )

    async def delete_template(
        self,
        owner_id: uuid.UUID | str,
        template_id: str,
    ) -> bool:
        """Permanently delete a mockup template image and manifest from S3/MinIO."""
        owner_str = str(owner_id)
        existing = await self.get_template(owner_id, template_id)
        if not existing:
            return False

        # 1. Delete image file
        try:
            await self._storage.delete(existing.storage_key)
        except Exception as err:
            logger.warning("failed_to_delete_template_image", key=existing.storage_key, error=str(err))

        # 2. Delete JSON manifest
        json_key = f"mockup-templates/{owner_str}/{existing.product_type}/{template_id}.json"
        try:
            await self._storage.delete(json_key)
        except Exception as err:
            logger.warning("failed_to_delete_template_manifest", key=json_key, error=str(err))

        return True
