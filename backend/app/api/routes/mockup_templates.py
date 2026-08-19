"""Mockup Templates API routes.

Provides endpoints for listing, uploading, and managing persistent custom mockup templates,
and compositing workflow master PNGs onto user-supplied or saved mockup templates.
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies import CurrentUser, SettingsDep, StorageDep, UowDep
from app.infrastructure.mockup_catalog import get_product_preset, normalize_mockup_product
from app.infrastructure.mockup_template_store import (
    MockupTemplateStore,
)

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
            detail=(
                f"Unsupported image type: {content_type}. Accepted formats are JPEG, PNG, and WebP."
            ),
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
        s = str(v).lower().strip().replace("_", "-")
        valid_modes = {
            "over",
            "multiply",
            "screen",
            "overlay",
            "soft-light",
            "hard-light",
            "darken",
            "lighten",
            "color-burn",
            "colour-burn",
            "color-dodge",
            "colour-dodge",
        }
        return s if s in valid_modes else "over"


class UploadTemplateRequest(BaseModel):
    name: str = "Custom Mockup"
    product_type: str = "tshirt"
    image_base64: str
    content_type: str = "image/jpeg"
    placement: PlacementSchema | None = None


class CompositeCustomMockupRequest(BaseModel):
    workflow_id: uuid.UUID
    product_type: str = "tshirt"
    master_asset_id: uuid.UUID | None = None
    template_id: str | None = None
    template_image_base64: str | None = None
    template_name: str | None = None
    save_as_template: bool = False
    placement: PlacementSchema | None = None
    target_asset_id: uuid.UUID | None = None
    is_cover: bool | None = None


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    product_type: str | None = None
    placement: PlacementSchema | None = None


class TemplateStatsResponse(BaseModel):
    total_templates: int
    by_product: dict[str, int]


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
    product_type: str | None = Query(
        None, description="Optional canonical product filter (e.g. tshirt, mug, tote_bag)"
    ),
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


@router.get("/stats", response_model=TemplateStatsResponse)
async def get_template_stats(
    user: CurrentUser,
    storage: StorageDep,
) -> TemplateStatsResponse:
    """Get aggregate template metrics and counts by product type."""
    store = MockupTemplateStore(storage)
    items = await store.list_templates(owner_id=user.id)
    by_prod: dict[str, int] = {}
    for item in items:
        p = item.product_type
        by_prod[p] = by_prod.get(p, 0) + 1
    return TemplateStatsResponse(
        total_templates=len(items),
        by_product=by_prod,
    )


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
        raise HTTPException(
            status_code=400, detail="Invalid base64 encoded template image."
        ) from None

    validate_image_payload(
        content,
        payload.content_type,
        max_bytes=settings.image_max_input_bytes,
    )

    canonical_type = normalize_mockup_product(payload.product_type) or payload.product_type
    preset = get_product_preset(canonical_type)

    placement_dict = (
        payload.placement.model_dump()
        if payload.placement
        else {
            "left_pct": preset.default_left_pct,
            "top_pct": preset.default_top_pct,
            "width_pct": preset.default_width_pct,
            "height_pct": preset.default_height_pct,
            "angle_deg": 0.0,
            "blend_mode": preset.default_blend_mode,
        }
    )

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


@router.patch("/{template_id}", response_model=MockupTemplateResponse)
async def update_template(
    template_id: str,
    payload: UpdateTemplateRequest,
    user: CurrentUser,
    storage: StorageDep,
) -> MockupTemplateResponse:
    """Update name, product_type, or placement coordinates of a saved mockup template."""
    store = MockupTemplateStore(storage)
    placement_dict = payload.placement.model_dump() if payload.placement else None
    item = await store.update_template(
        owner_id=user.id,
        template_id=template_id,
        name=payload.name,
        product_type=payload.product_type,
        placement=placement_dict,
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

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


@router.delete("/categories/{product_type}", status_code=status.HTTP_200_OK)
async def delete_category_templates_endpoint(
    product_type: str,
    user: CurrentUser,
    storage: StorageDep,
) -> dict[str, Any]:
    """Permanently delete a product category and all its saved templates
    for the authenticated owner.
    """
    store = MockupTemplateStore(storage)
    deleted_count = await store.delete_category_templates(
        owner_id=user.id, product_type=product_type
    )
    return {
        "product_type": product_type,
        "deleted_count": deleted_count,
        "status": "deleted",
    }


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    user: CurrentUser,
    storage: StorageDep,
) -> Response:
    """Permanently delete a mockup template and its S3 image from storage."""
    store = MockupTemplateStore(storage)
    success = await store.delete_template(owner_id=user.id, template_id=template_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/composite", response_model=CompositeMockupResponse)
async def composite_custom_mockup_endpoint(
    payload: CompositeCustomMockupRequest,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> CompositeMockupResponse:
    """Composite the workflow's master PNG onto a custom template photo."""
    from app.application.mockups import MockupCompositionError, MockupCompositionService
    from app.domain.errors import EntityNotFoundError

    service = MockupCompositionService(
        uow=uow,
        storage=storage,
        image_worker_url=settings.image_worker_url,
        image_max_input_bytes=settings.image_max_input_bytes,
    )

    try:
        result = await service.composite_custom_mockup(
            owner_id=user.id,
            workflow_id=payload.workflow_id,
            product_type=payload.product_type,
            template_id=payload.template_id,
            template_name=payload.template_name,
            template_image_base64=payload.template_image_base64,
            save_as_template=payload.save_as_template,
            placement=payload.placement.model_dump() if payload.placement else None,
            is_cover=payload.is_cover,
            target_asset_id=payload.target_asset_id,
            master_asset_id=payload.master_asset_id,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found."
        ) from None
    except (MockupCompositionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CompositeMockupResponse(
        mockup_url=result.mockup_url,
        asset_id=result.asset_id,
        product_type=result.product_type,
        template_id=result.template_id,
        template_name=result.template_name,
        is_cover=result.is_cover,
        listing_order=result.listing_order,
        width=result.width,
        height=result.height,
        format="jpeg",
    )
