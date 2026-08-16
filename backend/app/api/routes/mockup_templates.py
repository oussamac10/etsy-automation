"""Mockup Templates API routes.

Provides endpoints for listing, uploading, and managing persistent custom mockup templates,
and compositing workflow master PNGs onto user-supplied or saved mockup templates.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies import CurrentUser, SettingsDep, StorageDep, UowDep
from app.infrastructure.mockup_catalog import get_product_preset, normalize_mockup_product
from app.infrastructure.mockup_template_store import (
    CustomMockupPlacement,
    MockupTemplateItem,
    MockupTemplateStore,
)
from app.infrastructure.models import Asset

router = APIRouter(prefix="/mockup-templates", tags=["mockup-templates"])

ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}


def validate_image_payload(
    content: bytes,
    content_type: str,
    max_bytes: int = 40 * 1024 * 1024,
) -> None:
    """Validate image bytes, MIME type, and decodable header."""
    clean_mime = content_type.lower().strip()
    if clean_mime not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {content_type}. Accepted formats are JPEG, PNG, and WebP.",
        )

    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mockup template image exceeds {max_mb}MB limit.",
        )

    if len(content) < 16:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is too small to be a valid image.",
        )

    # Magic byte header checks
    is_jpeg = content.startswith(b"\xff\xd8\xff")
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP"

    if not (is_jpeg or is_png or is_webp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a valid decodable JPEG, PNG, or WebP image.",
        )


class PlacementSchema(BaseModel):
    left_pct: float = Field(default=0.25)
    top_pct: float = Field(default=0.25)
    width_pct: float = Field(default=0.50)
    height_pct: float = Field(default=0.50)
    angle_deg: float = Field(default=0.0)
    blend_mode: str = Field(default="multiply")

    @field_validator("left_pct", "top_pct", "width_pct", "height_pct", mode="before")
    @classmethod
    def normalize_pct(cls, v: Any) -> float:
        try:
            val = float(v)
        except (ValueError, TypeError):
            return 0.25
        if val > 1.0:
            val = val / 100.0
        return max(0.0, min(1.0, val))

    @field_validator("angle_deg", mode="before")
    @classmethod
    def normalize_angle(cls, v: Any) -> float:
        try:
            val = float(v)
        except (ValueError, TypeError):
            return 0.0
        return max(-180.0, min(180.0, val))

    @field_validator("blend_mode", mode="before")
    @classmethod
    def normalize_blend(cls, v: Any) -> str:
        s = str(v).lower().strip()
        return "over" if s == "over" else "multiply"


class UploadTemplateRequest(BaseModel):
    name: str = "Custom Mockup"
    product_type: str = "tshirt"
    image_base64: str
    content_type: str = "image/jpeg"
    placement: PlacementSchema | None = None


class CompositeCustomMockupRequest(BaseModel):
    workflow_id: uuid.UUID
    product_type: str = "tshirt"
    template_id: str | None = None
    template_image_base64: str | None = None
    template_name: str | None = None
    save_as_template: bool = False
    placement: PlacementSchema | None = None
    target_asset_id: uuid.UUID | None = None
    is_cover: bool | None = None


class MockupTemplateResponse(BaseModel):
    id: str
    name: str
    product_type: str
    url: str
    placement: PlacementSchema
    created_at: str
    is_custom: bool = True


class CompositeMockupResponse(BaseModel):
    mockup_url: str
    asset_id: uuid.UUID
    product_type: str
    template_id: str | None = None
    template_name: str | None = None
    is_cover: bool = False
    listing_order: int = 1
    width: int
    height: int
    format: str


@router.get("", response_model=list[MockupTemplateResponse])
async def list_templates(
    user: CurrentUser,
    storage: StorageDep,
    product_type: str | None = Query(None, description="Optional canonical product filter (e.g. tshirt, mug, tote_bag)"),
) -> list[MockupTemplateResponse]:
    """List all saved custom mockup templates for the authenticated owner."""
    canonical_type = normalize_mockup_product(product_type) if product_type else None
    store = MockupTemplateStore(storage)
    items = await store.list_templates(owner_id=user.id, product_type=canonical_type)
    return [
        MockupTemplateResponse(
            id=item.id,
            name=item.name,
            product_type=item.product_type,
            url=item.url,
            placement=PlacementSchema(
                left_pct=item.placement.left_pct,
                top_pct=item.placement.top_pct,
                width_pct=item.placement.width_pct,
                height_pct=item.placement.height_pct,
                angle_deg=item.placement.angle_deg,
                blend_mode=item.placement.blend_mode,
            ),
            created_at=item.created_at,
            is_custom=item.is_custom,
        )
        for item in items
    ]


@router.post("/upload", response_model=MockupTemplateResponse, status_code=status.HTTP_201_CREATED)
async def upload_template(
    payload: UploadTemplateRequest,
    user: CurrentUser,
    storage: StorageDep,
    settings: SettingsDep,
) -> MockupTemplateResponse:
    """Upload and save a new custom mockup template image for the authenticated owner."""
    try:
        content = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 encoded template image.")

    validate_image_payload(
        content,
        payload.content_type,
        max_bytes=settings.image_max_input_bytes,
    )

    canonical_type = normalize_mockup_product(payload.product_type) or payload.product_type
    preset = get_product_preset(canonical_type)

    placement_dict = payload.placement.model_dump() if payload.placement else {
        "left_pct": preset.default_left_pct,
        "top_pct": preset.default_top_pct,
        "width_pct": preset.default_width_pct,
        "height_pct": preset.default_height_pct,
        "angle_deg": 0.0,
        "blend_mode": preset.default_blend_mode,
    }

    store = MockupTemplateStore(storage)
    item = await store.save_template(
        owner_id=user.id,
        name=payload.name,
        product_type=canonical_type,
        image_bytes=content,
        content_type=payload.content_type,
        placement=placement_dict,
    )

    return MockupTemplateResponse(
        id=item.id,
        name=item.name,
        product_type=item.product_type,
        url=item.url,
        placement=PlacementSchema(
            left_pct=item.placement.left_pct,
            top_pct=item.placement.top_pct,
            width_pct=item.placement.width_pct,
            height_pct=item.placement.height_pct,
            angle_deg=item.placement.angle_deg,
            blend_mode=item.placement.blend_mode,
        ),
        created_at=item.created_at,
        is_custom=item.is_custom,
    )


@router.post("/composite", response_model=CompositeMockupResponse)
async def composite_custom_mockup_endpoint(
    payload: CompositeCustomMockupRequest,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> CompositeMockupResponse:
    """Composite the workflow's master PNG onto a custom template photo."""
    # 1. Load workflow and verify owner isolation
    workflow = await uow.workflows.get(payload.workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")

    canonical_prod = normalize_mockup_product(payload.product_type) or payload.product_type
    preset = get_product_preset(canonical_prod)

    # 2. Find true production master PNG (exclude all mockup assets)
    master_asset: Asset | None = None
    jobs = await uow.production_jobs.list_for_workflow(payload.workflow_id)
    if jobs:
        latest_job = jobs[-1]
        if latest_job.output_asset_id:
            master_asset = await uow.assets.get(latest_job.output_asset_id)

    if not master_asset:
        assets = await uow.assets.list_for_workflow(payload.workflow_id)
        # Find master PNG with profile etsy-png-standard or storage_key ending in master.png
        master_asset = next(
            (
                a for a in assets
                if (a.storage_key.endswith("/master.png") or (a.provenance and a.provenance.get("profile") == "etsy-png-standard"))
                and "/mockups/" not in a.storage_key
                and "mockup" not in a.storage_key
                and (not a.provenance or a.provenance.get("asset_type") != "mockup")
            ),
            None,
        )

    if not master_asset:
        # Fallback to artwork candidate asset (strictly not a mockup)
        assets = await uow.assets.list_for_workflow(payload.workflow_id)
        artwork_assets = [
            a for a in assets
            if a.artwork_job_id is not None
            and "/mockups/" not in a.storage_key
            and (not a.provenance or a.provenance.get("asset_type") != "mockup")
        ]
        if artwork_assets:
            master_asset = artwork_assets[0]

    if not master_asset:
        raise HTTPException(status_code=400, detail="No production master PNG available for this workflow.")

    # 3. Read master PNG bytes
    master_bytes = await storage.get(master_asset.storage_key)

    # 4. Resolve template bytes & placement
    store = MockupTemplateStore(storage)
    template_bytes: bytes | None = None
    resolved_placement: dict = payload.placement.model_dump() if payload.placement else {
        "left_pct": preset.default_left_pct,
        "top_pct": preset.default_top_pct,
        "width_pct": preset.default_width_pct,
        "height_pct": preset.default_height_pct,
        "angle_deg": 0.0,
        "blend_mode": preset.default_blend_mode,
    }
    resolved_template_id = payload.template_id
    resolved_template_name = payload.template_name or f"{canonical_prod.replace('_', ' ').capitalize()} Mockup"

    resolved_template_storage_key: str | None = None
    if payload.template_image_base64:
        try:
            template_bytes = base64.b64decode(payload.template_image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 encoded template image.")

        validate_image_payload(
            template_bytes,
            "image/jpeg",
            max_bytes=settings.image_max_input_bytes,
        )

        if payload.save_as_template:
            saved_item = await store.save_template(
                owner_id=user.id,
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
            raw_tpl_key = f"mockup-templates/{user.id}/{canonical_prod}/source_{tpl_img_id}.jpg"
            await storage.put(raw_tpl_key, template_bytes, content_type="image/jpeg")
            resolved_template_storage_key = raw_tpl_key
    elif payload.template_id:
        existing_template = await store.get_template(owner_id=user.id, template_id=payload.template_id)
        if not existing_template:
            raise HTTPException(status_code=404, detail="Selected template not found.")
        template_bytes = await storage.get(existing_template.storage_key)
        resolved_template_storage_key = existing_template.storage_key
        resolved_template_name = payload.template_name or existing_template.name
        if not payload.placement:
            resolved_placement = {
                "left_pct": existing_template.placement.left_pct,
                "top_pct": existing_template.placement.top_pct,
                "width_pct": existing_template.placement.width_pct,
                "height_pct": existing_template.placement.height_pct,
                "angle_deg": existing_template.placement.angle_deg,
                "blend_mode": existing_template.placement.blend_mode,
            }
    else:
        raise HTTPException(status_code=400, detail="Either template_image_base64 or template_id must be provided.")

    if not template_bytes:
        raise HTTPException(status_code=400, detail="Failed to read template image.")

    # 5. Call image-worker /pipeline/custom-mockup
    image_worker_url = settings.image_worker_url.rstrip("/")
    worker_payload = {
        "artwork_base64": base64.b64encode(master_bytes).decode("utf-8"),
        "template_base64": base64.b64encode(template_bytes).decode("utf-8"),
        "placement": resolved_placement,
        "format": "jpeg",
        "quality": 92,
    }

    async with httpx.AsyncClient(timeout=45.0) as http_client:
        resp = await http_client.post(f"{image_worker_url}/pipeline/custom-mockup", json=worker_payload)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Image worker failed to composite custom mockup: {resp.text[:200]}",
            )
        result_data = resp.json()

    composited_bytes = base64.b64decode(result_data["mockup_base64"])
    out_w = result_data.get("width", 1200)
    out_h = result_data.get("height", 1200)

    # 6. Fetch existing workflow mockup assets to determine ordering and cover status
    all_wf_assets = await uow.assets.list_for_workflow(payload.workflow_id)
    existing_mockups = [
        a for a in all_wf_assets
        if (a.provenance and a.provenance.get("asset_type") == "mockup") or "/mockups/" in a.storage_key
    ]

    target_asset: Asset | None = None
    if payload.target_asset_id:
        target_asset = next((a for a in existing_mockups if a.id == payload.target_asset_id), None)

    # Calculate listing order and cover status
    if target_asset and target_asset.provenance:
        order = int(str(target_asset.provenance.get("listing_order", "1") or "1"))
        is_cover = bool(target_asset.provenance.get("is_cover", False))
        if payload.is_cover is not None:
            is_cover = payload.is_cover
    else:
        existing_orders = [
            int(str(m.provenance.get("listing_order", "0") or "0"))
            for m in existing_mockups
            if m.provenance
        ]
        order = (max(existing_orders) + 1) if existing_orders else 1
        is_cover = True if len(existing_mockups) == 0 else bool(payload.is_cover)

    # If this asset is set as cover, unset cover on all other mockups
    if is_cover:
        for other in existing_mockups:
            if target_asset and other.id == target_asset.id:
                continue
            if other.provenance and other.provenance.get("is_cover"):
                other.provenance = dict(other.provenance, is_cover=False)
                await uow.session.flush()

    mockup_id = target_asset.id if target_asset else uuid.uuid4()
    mockup_storage_key = f"production/{payload.workflow_id}/mockups/custom_{canonical_prod}_{mockup_id}.jpg"
    await storage.put(mockup_storage_key, composited_bytes, content_type="image/jpeg")
    mockup_url = await storage.signed_url(mockup_storage_key, expires_in_seconds=86400 * 7)

    mock_sha256 = hashlib.sha256(composited_bytes).hexdigest()
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
        "is_cover": is_cover,
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
        await uow.session.flush()
    else:
        custom_asset = Asset(
            id=mockup_id,
            workflow_id=payload.workflow_id,
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
        await uow.assets.add(custom_asset)

    await uow.session.commit()

    return CompositeMockupResponse(
        mockup_url=mockup_url,
        asset_id=mockup_id,
        product_type=canonical_prod,
        template_id=resolved_template_id,
        template_name=resolved_template_name,
        is_cover=is_cover,
        listing_order=order,
        width=out_w,
        height=out_h,
        format="jpeg",
    )
