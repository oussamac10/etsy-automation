"""Persistent Mockup Template Store backed by S3 / MinIO object storage.

Allows storing, retrieving, and reusing custom mockup templates per owner and product type
with exact placement coordinates and texture blend modes.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from app.domain.mockup_products import get_product_preset, normalize_product_type
from app.providers.s3 import S3ObjectStorage

logger = structlog.get_logger(__name__)


@dataclass
class CustomMockupPlacement:
    id: str | None = None
    left_pct: float = 0.25
    top_pct: float = 0.25
    width_pct: float = 0.50
    height_pct: float = 0.50
    angle_deg: float = 0.0
    blend_mode: str = "multiply"  # "multiply" for realistic shadows/wrinkles, "over" for opaque
    artwork_source_id: str | None = None


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
    placements: list[CustomMockupPlacement] = field(default_factory=list)


def _parse_single_placement(
    p_data: dict[str, Any] | CustomMockupPlacement | None,
    preset: Any,
) -> CustomMockupPlacement:
    if isinstance(p_data, CustomMockupPlacement):
        return p_data
    if isinstance(p_data, dict):
        return CustomMockupPlacement(
            id=str(p_data["id"]) if p_data.get("id") else None,
            left_pct=float(p_data.get("left_pct", getattr(preset, "default_left_pct", 0.25))),
            top_pct=float(p_data.get("top_pct", getattr(preset, "default_top_pct", 0.25))),
            width_pct=float(p_data.get("width_pct", getattr(preset, "default_width_pct", 0.50))),
            height_pct=float(p_data.get("height_pct", getattr(preset, "default_height_pct", 0.50))),
            angle_deg=float(p_data.get("angle_deg", 0.0)),
            blend_mode=str(
                p_data.get("blend_mode", getattr(preset, "default_blend_mode", "multiply"))
            ),
            artwork_source_id=str(p_data["artwork_source_id"])
            if p_data.get("artwork_source_id")
            else None,
        )
    return CustomMockupPlacement(
        left_pct=getattr(preset, "default_left_pct", 0.25),
        top_pct=getattr(preset, "default_top_pct", 0.25),
        width_pct=getattr(preset, "default_width_pct", 0.50),
        height_pct=getattr(preset, "default_height_pct", 0.50),
        blend_mode=getattr(preset, "default_blend_mode", "multiply"),
    )


class MockupTemplateStore:
    """Store and retrieve persistent custom mockup templates from S3 scoped per owner."""

    def __init__(self, storage: S3ObjectStorage) -> None:
        self._storage = storage

    async def list_templates(
        self,
        owner_id: uuid.UUID | str,
        product_type: str | None = None,
    ) -> list[MockupTemplateItem]:
        """List all saved mockup templates for an owner.
        Optionally filtered by canonical product type.
        """
        owner_str = str(owner_id)
        canonical_target = normalize_product_type(product_type) if product_type else None
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
                    placements_data = meta.get("placements", [])
                    created_at = meta.get("created_at", datetime.now(UTC).isoformat())

                    if not t_img_key:
                        continue

                    # Generate presigned URL for thumbnail / display
                    url = await self._storage.signed_url(t_img_key, expires_in_seconds=86400 * 7)

                    preset = get_product_preset(t_prod)
                    placements_list: list[CustomMockupPlacement] = []
                    if isinstance(placements_data, list) and len(placements_data) > 0:
                        for p in placements_data:
                            placements_list.append(_parse_single_placement(p, preset))
                    else:
                        placements_list.append(_parse_single_placement(placement_data, preset))

                    primary_placement = placements_list[0]

                    templates.append(
                        MockupTemplateItem(
                            id=t_id,
                            owner_id=t_owner,
                            name=t_name,
                            product_type=t_prod,
                            storage_key=t_img_key,
                            url=url,
                            placement=primary_placement,
                            placements=placements_list,
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
        placement: CustomMockupPlacement | dict[str, Any] | None = None,
        placements: Sequence[CustomMockupPlacement | dict[str, Any]] | None = None,
    ) -> MockupTemplateItem:
        """Save a new custom mockup template image and its manifest to S3 for an owner."""
        owner_str = str(owner_id)
        canonical = normalize_product_type(product_type) or (
            product_type.strip().lower().replace(" ", "_") if product_type else "custom_product"
        )
        template_id = str(uuid.uuid4())
        preset = get_product_preset(canonical)

        ext = (
            "png"
            if "png" in content_type.lower()
            else ("webp" if "webp" in content_type.lower() else "jpg")
        )
        image_key = f"mockup-templates/{owner_str}/{canonical}/{template_id}.{ext}"
        json_key = f"mockup-templates/{owner_str}/{canonical}/{template_id}.json"

        # 1. Upload template image
        await self._storage.put(image_key, image_bytes, content_type=content_type)

        # 2. Build placements list
        placements_list: list[CustomMockupPlacement] = []
        if placements and len(placements) > 0:
            for p in placements:
                placements_list.append(_parse_single_placement(p, preset))
        else:
            placements_list.append(_parse_single_placement(placement, preset))

        primary_placement = placements_list[0]

        tpl_name = name.strip() or f"Custom {canonical.capitalize()} Mockup"
        created_at_str = datetime.now(UTC).isoformat()
        manifest: dict[str, Any] = {
            "id": template_id,
            "owner_id": owner_str,
            "name": tpl_name,
            "product_type": canonical,
            "storage_key": image_key,
            "placement": asdict(primary_placement),
            "placements": [asdict(p) for p in placements_list],
            "created_at": created_at_str,
            "is_custom": True,
        }

        # 3. Upload manifest JSON
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        await self._storage.put(json_key, manifest_bytes, content_type="application/json")

        url = await self._storage.signed_url(image_key, expires_in_seconds=86400 * 7)

        return MockupTemplateItem(
            id=template_id,
            owner_id=owner_str,
            name=tpl_name,
            product_type=canonical,
            storage_key=image_key,
            url=url,
            placement=primary_placement,
            placements=placements_list,
            created_at=created_at_str,
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
        placement: CustomMockupPlacement | dict[str, Any] | None = None,
        placements: Sequence[CustomMockupPlacement | dict[str, Any]] | None = None,
        product_type: str | None = None,
    ) -> MockupTemplateItem | None:
        """Update metadata, name, or placement coordinates of an existing template."""
        owner_str = str(owner_id)
        existing = await self.get_template(owner_id, template_id)
        if not existing:
            return None

        canonical = normalize_product_type(product_type) or existing.product_type
        json_key = f"mockup-templates/{owner_str}/{existing.product_type}/{template_id}.json"
        preset = get_product_preset(canonical)

        # Build updated placements
        placements_list: list[CustomMockupPlacement] = []
        if placements is not None and len(placements) > 0:
            for p in placements:
                placements_list.append(_parse_single_placement(p, preset))
        elif placement is not None:
            placements_list.append(_parse_single_placement(placement, preset))
        else:
            placements_list = existing.placements if existing.placements else [existing.placement]

        primary_placement = placements_list[0]
        updated_name = name.strip() if name and name.strip() else existing.name

        manifest = {
            "id": template_id,
            "owner_id": owner_str,
            "name": updated_name,
            "product_type": canonical,
            "storage_key": existing.storage_key,
            "placement": asdict(primary_placement),
            "placements": [asdict(p) for p in placements_list],
            "created_at": existing.created_at,
            "updated_at": datetime.now(UTC).isoformat(),
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
            placement=primary_placement,
            placements=placements_list,
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
            logger.warning(
                "failed_to_delete_template_image", key=existing.storage_key, error=str(err)
            )

        # 2. Delete JSON manifest
        json_key = f"mockup-templates/{owner_str}/{existing.product_type}/{template_id}.json"
        try:
            await self._storage.delete(json_key)
        except Exception as err:
            logger.warning("failed_to_delete_template_manifest", key=json_key, error=str(err))

        return True

    async def delete_category_templates(
        self,
        owner_id: uuid.UUID | str,
        product_type: str,
    ) -> int:
        """Permanently delete all templates in a specific product category for an owner."""
        canonical = normalize_product_type(product_type) or product_type
        templates = await self.list_templates(owner_id=owner_id, product_type=canonical)
        deleted_count = 0
        for t in templates:
            success = await self.delete_template(owner_id=owner_id, template_id=t.id)
            if success:
                deleted_count += 1
        return deleted_count
