"""Mockup Templates API routes.

Provides endpoints for listing, uploading, and managing persistent custom mockup templates,
and compositing workflow master PNGs onto user-supplied or saved mockup templates.
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.api.dependencies import CurrentUser, SettingsDep, StorageDep, UowDep
from app.domain.workflow import JobStatus
from app.infrastructure.mockup_catalog import normalize_mockup_product
from app.infrastructure.mockup_template_store import (
    CustomMockupPlacement,
    MockupTemplateItem,
    MockupTemplateStore,
)
from app.infrastructure.models import Asset, ProductionJob
from app.settings import Settings

router = APIRouter(prefix="/mockup-templates", tags=["mockup-templates"])


class PlacementSchema(BaseModel):
    left_pct: float = Field(default=0.25, ge=0.0, le=0.95)
    top_pct: float = Field(default=0.25, ge=0.0, le=0.95)
    width_pct: float = Field(default=0.50, ge=0.05, le=1.0)
    height_pct: float = Field(default=0.50, ge=0.05, le=1.0)
    angle_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    blend_mode: str = Field(default="multiply", pattern="^(multiply|over)$")


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
    product_type: str
    template_id: str | None = None
    width: int
    height: int
    format: str


@router.get("", response_model=list[MockupTemplateResponse])
async def list_templates(
    storage: StorageDep,
    product_type: str | None = Query(None, description="Optional canonical product filter (e.g. tshirt, mug)"),
) -> list[MockupTemplateResponse]:
    """List all saved custom mockup templates."""
    store = MockupTemplateStore(storage)
    items = await store.list_templates(product_type)
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
    storage: StorageDep,
) -> MockupTemplateResponse:
    """Upload and save a new custom mockup template image from base64."""
    try:
        content = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 encoded template image.")

    if len(content) > 35 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Mockup template image exceeds 35MB limit.")

    placement_dict = payload.placement.model_dump() if payload.placement else {}

    store = MockupTemplateStore(storage)
    item = await store.save_template(
        name=payload.name,
        product_type=payload.product_type,
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
    uow: UowDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> CompositeMockupResponse:
    """Composite the workflow's master PNG onto a custom template photo."""
    # 1. Load workflow
    workflow = await uow.workflows.get(payload.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    # 2. Find production master PNG or source artwork asset
    assets = await uow.assets.list_for_workflow(payload.workflow_id)
    master_asset = next(
        (a for a in assets if a.storage_key.startswith("production/") and a.storage_key.endswith(".png")),
        None,
    )
    if not master_asset:
        # Fallback to artwork candidate asset
        artwork_assets = [a for a in assets if a.artwork_job_id is not None]
        if artwork_assets:
            master_asset = artwork_assets[0]

    if not master_asset:
        raise HTTPException(status_code=400, detail="No production master PNG available for this workflow.")

    # 3. Read master PNG bytes
    master_bytes = await storage.get(master_asset.storage_key)

    # 4. Resolve template bytes & placement
    store = MockupTemplateStore(storage)
    template_bytes: bytes | None = None
    resolved_placement: dict = payload.placement.model_dump() if payload.placement else {}
    resolved_template_id = payload.template_id

    if payload.template_image_base64:
        try:
            template_bytes = base64.b64decode(payload.template_image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 encoded template image.")

        if payload.save_as_template:
            saved_item = await store.save_template(
                name=payload.template_name or f"Custom {payload.product_type.capitalize()} Mockup",
                product_type=payload.product_type,
                image_bytes=template_bytes,
                content_type="image/jpeg",
                placement=resolved_placement,
            )
            resolved_template_id = saved_item.id
    elif payload.template_id:
        existing_template = await store.get_template(payload.template_id)
        if not existing_template:
            raise HTTPException(status_code=404, detail="Selected template not found.")
        template_bytes = await storage.get(existing_template.storage_key)
        if not resolved_placement:
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

    # 6. Save composited mockup to S3
    canonical_prod = normalize_mockup_product(payload.product_type) or "custom"
    mockup_id = uuid.uuid4()
    mockup_storage_key = f"production/{payload.workflow_id}/mockups/custom_{canonical_prod}_{mockup_id}.jpg"
    await storage.put(mockup_storage_key, composited_bytes, content_type="image/jpeg")
    mockup_url = await storage.signed_url(mockup_storage_key, expires_in_seconds=86400 * 7)

    # 7. Record as workflow Asset
    import hashlib
    mock_sha256 = hashlib.sha256(composited_bytes).hexdigest()
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
        provenance={
            "phase": 7,
            "asset_type": "mockup",
            "is_custom": True,
            "product_type": canonical_prod,
            "template_id": resolved_template_id,
            "source_asset_id": str(master_asset.id),
        },
    )
    await uow.assets.add(custom_asset)
    await uow.session.commit()

    return CompositeMockupResponse(
        mockup_url=mockup_url,
        product_type=canonical_prod,
        template_id=resolved_template_id,
        width=out_w,
        height=out_h,
        format="jpeg",
    )
