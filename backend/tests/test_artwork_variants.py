"""Unit, integration, and regression tests for Deterministic Artwork Color Variant Engine and Quality Validation."""

from __future__ import annotations

from datetime import UTC, datetime
import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

from app.api.routes.artwork_variants import (
    approve_artwork_variant_endpoint,
    create_artwork_variant_endpoint,
    delete_artwork_variant_endpoint,
    list_artwork_variants_endpoint,
    reject_artwork_variant_endpoint,
    to_variant_response,
)
from app.api.schemas import CreateArtworkVariantRequest
from app.application.artwork_variants import ArtworkVariantError, ArtworkVariantService
from app.application.package import CustomerPackageService
from app.domain.artwork_variants import (
    DEFAULT_DARK_SHIRT_TARGET,
    ArtworkVariantValidationError,
    VariantStatus,
    VariantType,
    compute_variant_filename,
    detect_baked_checkerboard,
    filter_workflow_artwork_variants,
    is_png_format,
    is_valid_artwork_variant_asset,
    recolor_artwork_variant,
    sanitize_hex_color,
    validate_artwork_variant,
)
from app.infrastructure.models import Asset, ListingDraft, ProductWorkflow, User
from app.providers.fake import FakeImageProvider


def _create_sample_master_png() -> bytes:
    """Create a realistic sample RGBA master PNG with transparent background, black lines, and vibrant colors."""
    img = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Black outline & text (10, 10, 10, 255)
    draw.rectangle([50, 50, 200, 200], fill=(10, 10, 10, 255))
    # 2. Dark brown vintage line (40, 30, 20, 255)
    draw.rectangle([250, 50, 400, 200], fill=(40, 30, 20, 255))
    # 3. Vibrant Orange petal (240, 100, 20, 255)
    draw.rectangle([450, 50, 600, 200], fill=(240, 100, 20, 255))
    # 4. Vibrant Teal leaf (20, 160, 150, 255)
    draw.rectangle([50, 250, 200, 400], fill=(20, 160, 150, 255))
    # 5. Crisp White highlight (255, 255, 255, 255)
    draw.rectangle([250, 250, 400, 400], fill=(255, 255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(300, 300))
    return buf.getvalue()


class TestArtworkVariantsDomain:
    def test_sanitize_hex_color(self) -> None:
        assert sanitize_hex_color("#FF5733") == "#FF5733"
        assert sanitize_hex_color("FF5733") == "#FF5733"
        assert sanitize_hex_color("#fff") == "#FFFFFF"
        assert sanitize_hex_color("invalid") == "#FFFFFF"
        assert sanitize_hex_color(None) == "#FFFFFF"

    def test_is_png_format(self) -> None:
        png_bytes = _create_sample_master_png()
        assert is_png_format(png_bytes) is True
        assert is_png_format(b"\xff\xd8\xff\xe0\x00\x10JFIF") is False
        assert is_png_format(b"RIFF....WEBP") is False

    def test_is_valid_artwork_variant_asset(self) -> None:
        assert is_valid_artwork_variant_asset({"kind": "artwork_variant", "variant_type": "dark_shirt"}) is True
        assert is_valid_artwork_variant_asset({"kind": "customer_package"}) is False
        assert is_valid_artwork_variant_asset({"asset_type": "mockup"}) is False
        assert is_valid_artwork_variant_asset(None) is False

    def test_compute_variant_filename(self) -> None:
        assert compute_variant_filename("Shop_Fox", VariantType.DARK_SHIRT) == "Shop_Fox_PNG_Dark_Shirt.png"
        assert compute_variant_filename("Shop_Fox", VariantType.LIGHT_SHIRT) == "Shop_Fox_PNG_Light_Shirt.png"
        assert compute_variant_filename("Shop_Fox", VariantType.CUSTOM, "#E85D04") == "Shop_Fox_PNG_Custom_E85D04.png"

    def test_filter_workflow_artwork_variants(self) -> None:
        v1 = MagicMock(spec=Asset)
        v1.provenance = {"kind": "artwork_variant", "variant_status": VariantStatus.APPROVED.value}
        v1.created_at = datetime(2026, 1, 1, tzinfo=UTC)

        v2 = MagicMock(spec=Asset)
        v2.provenance = {"kind": "artwork_variant", "variant_status": VariantStatus.READY.value}
        v2.created_at = datetime(2026, 1, 2, tzinfo=UTC)

        mockup = MagicMock(spec=Asset)
        mockup.provenance = {"asset_type": "mockup"}

        filtered = filter_workflow_artwork_variants([v2, mockup, v1])
        assert len(filtered) == 2
        assert filtered[0] == v1  # Approved first
        assert filtered[1] == v2


class TestDeterministicRecolorEngine:
    def test_recolor_dark_shirt_preserves_alpha_and_colors(self) -> None:
        master_bytes = _create_sample_master_png()
        variant_bytes, report = recolor_artwork_variant(
            source_bytes=master_bytes,
            variant_type=VariantType.DARK_SHIRT,
            target_color_hex=DEFAULT_DARK_SHIRT_TARGET,
        )

        assert is_png_format(variant_bytes) is True
        assert report["is_valid"] is True
        assert report["has_real_alpha"] is True
        assert report["checkerboard_free"] is True

        out_img = Image.open(io.BytesIO(variant_bytes))
        src_img = Image.open(io.BytesIO(master_bytes))

        assert out_img.size == src_img.size
        assert out_img.mode == "RGBA"

        # 1. Byte-identical alpha channel
        _, _, _, src_a = src_img.split()
        _, _, _, out_a = out_img.split()
        assert out_a.tobytes() == src_a.tobytes()

        # 2. Transparent background preserved
        assert out_img.getpixel((10, 10)) == (0, 0, 0, 0)

        # 3. Black line recolored to warm cream
        recolored_black = out_img.getpixel((100, 100))
        assert recolored_black[0] > 190  # R
        assert recolored_black[1] > 180  # G
        assert recolored_black[2] > 150  # B
        assert recolored_black[3] == 255  # Alpha intact

        # 4. Vibrant orange preserved exactly
        orange_pixel = out_img.getpixel((500, 100))
        assert orange_pixel == (240, 100, 20, 255)

        # 5. Vibrant teal preserved exactly
        teal_pixel = out_img.getpixel((100, 300))
        assert teal_pixel == (20, 160, 150, 255)

    def test_recolor_light_shirt_recolors_white_to_charcoal(self) -> None:
        master_bytes = _create_sample_master_png()
        variant_bytes, report = recolor_artwork_variant(
            source_bytes=master_bytes,
            variant_type=VariantType.LIGHT_SHIRT,
        )

        out_img = Image.open(io.BytesIO(variant_bytes))

        # White highlight (250, 250) recolored to dark charcoal
        charcoal_pixel = out_img.getpixel((300, 300))
        assert charcoal_pixel[0] < 50
        assert charcoal_pixel[1] < 50
        assert charcoal_pixel[2] < 50
        assert charcoal_pixel[3] == 255

        # Vibrant orange preserved
        assert out_img.getpixel((500, 100)) == (240, 100, 20, 255)


class TestVariantValidationGuards:
    def test_reject_jpeg_format_with_explicit_error(self) -> None:
        master_bytes = _create_sample_master_png()
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"

        with pytest.raises(ArtworkVariantValidationError, match="Variant provider returned JPEG. Transparent PNG required."):
            validate_artwork_variant(
                source_bytes=master_bytes,
                variant_bytes=jpeg_bytes,
                variant_type=VariantType.DARK_SHIRT,
            )

    def test_reject_missing_alpha_with_explicit_error(self) -> None:
        master_bytes = _create_sample_master_png()

        # Create opaque RGB image without alpha
        opaque_img = Image.new("RGBA", (800, 800), (255, 255, 255, 255))
        buf = io.BytesIO()
        opaque_img.save(buf, format="PNG")
        opaque_png_bytes = buf.getvalue()

        with pytest.raises(ArtworkVariantValidationError, match="Generated variant lacks transparency"):
            validate_artwork_variant(
                source_bytes=master_bytes,
                variant_bytes=opaque_png_bytes,
                variant_type=VariantType.DARK_SHIRT,
            )

    def test_reject_baked_checkerboard_pattern(self) -> None:
        # Create an image with baked gray/white checkerboard in corner
        w, h = 800, 800
        img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw alternating gray/white 10x10 squares in corner (0,0) to (100,100)
        for y in range(0, 100, 10):
            for x in range(0, 100, 10):
                color = (204, 204, 204, 255) if ((x // 10 + y // 10) % 2 == 0) else (255, 255, 255, 255)
                draw.rectangle([x, y, x + 9, y + 9], fill=color)

        assert detect_baked_checkerboard(img) is True

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        checker_bytes = buf.getvalue()

        master_bytes = _create_sample_master_png()
        with pytest.raises(ArtworkVariantValidationError, match="Detected baked checkerboard pattern"):
            validate_artwork_variant(
                source_bytes=master_bytes,
                variant_bytes=checker_bytes,
                variant_type=VariantType.DARK_SHIRT,
            )


class TestArtworkVariantService:
    @pytest.mark.asyncio
    async def test_generate_variant_creates_derived_asset(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        master_asset_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id

        master_bytes = _create_sample_master_png()

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_asset_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.width = 800
        master_asset.height = 800
        master_asset.mime_type = "image/png"
        master_asset.provenance = {"profile": "etsy-png-standard"}

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.get = AsyncMock(return_value=master_asset)
        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset])
        uow.concepts.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.add = AsyncMock()
        uow.commit = AsyncMock()

        storage = MagicMock()
        storage.get = AsyncMock(return_value=master_bytes)
        storage.put = AsyncMock(return_value=MagicMock(storage_key=f"workflows/{workflow_id}/variants/1/dark_shirt.png"))

        fake_provider = FakeImageProvider()
        service = ArtworkVariantService(storage=storage, image_provider=fake_provider)

        variant = await service.generate_variant(
            workflow_id=workflow_id,
            owner_id=owner_id,
            variant_type=VariantType.DARK_SHIRT,
            uow=uow,
        )

        assert variant is not None
        assert variant.derived_from_id == master_asset_id
        assert variant.has_alpha is True
        assert variant.provenance["kind"] == "artwork_variant"
        assert variant.provenance["variant_type"] == "dark_shirt"
        assert variant.provenance["variant_status"] == VariantStatus.READY.value
        assert variant.quality_check["is_valid"] is True
        uow.assets.add.assert_called_once()
        uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_and_reject_variant(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        variant_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id

        variant_asset = MagicMock(spec=Asset)
        variant_asset.id = variant_id
        variant_asset.workflow_id = workflow_id
        variant_asset.provenance = {"kind": "artwork_variant", "variant_status": VariantStatus.READY.value}

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.assets.get = AsyncMock(return_value=variant_asset)
        uow.commit = AsyncMock()

        storage = MagicMock()
        service = ArtworkVariantService(storage=storage, image_provider=FakeImageProvider())

        # Approve
        approved = await service.approve_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=owner_id,
            uow=uow,
        )
        assert approved.provenance["variant_status"] == VariantStatus.APPROVED.value

        # Reject
        rejected = await service.reject_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=owner_id,
            uow=uow,
        )
        assert rejected.provenance["variant_status"] == VariantStatus.REJECTED.value

    @pytest.mark.asyncio
    async def test_delete_variant(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        variant_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id

        variant_asset = MagicMock(spec=Asset)
        variant_asset.id = variant_id
        variant_asset.workflow_id = workflow_id
        variant_asset.storage_key = "workflows/1/variants/1/dark.png"
        variant_asset.provenance = {"kind": "artwork_variant"}

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.assets.get = AsyncMock(return_value=variant_asset)
        uow.assets.delete = AsyncMock()
        uow.commit = AsyncMock()

        storage = MagicMock()
        storage.delete = AsyncMock()

        service = ArtworkVariantService(storage=storage, image_provider=FakeImageProvider())
        await service.delete_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=owner_id,
            uow=uow,
        )

        uow.assets.delete.assert_called_once_with(variant_asset)
        storage.delete.assert_called_once_with(variant_asset.storage_key)


class TestArtworkVariantRoutes:
    @pytest.mark.asyncio
    async def test_create_and_list_endpoints(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        master_id = uuid.uuid4()

        user = MagicMock(spec=User)
        user.id = owner_id

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id

        master_bytes = _create_sample_master_png()

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.width = 800
        master_asset.height = 800
        master_asset.mime_type = "image/png"
        master_asset.provenance = {"profile": "etsy-png-standard"}

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.get = AsyncMock(return_value=master_asset)
        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset])
        uow.concepts.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.add = AsyncMock()
        uow.commit = AsyncMock()

        storage = MagicMock()
        storage.get = AsyncMock(return_value=master_bytes)
        storage.put = AsyncMock(return_value=MagicMock(storage_key=f"workflows/{workflow_id}/variants/1/dark_shirt.png"))
        storage.signed_url = AsyncMock(return_value="https://storage.test/dark_shirt.png")

        settings = MagicMock()
        settings.provider_mode = "fake"

        # 1. Create Variant
        req = CreateArtworkVariantRequest(variant_type="dark_shirt", target_color="#F5E6C8")
        resp = await create_artwork_variant_endpoint(
            workflow_id=workflow_id,
            payload=req,
            user=user,
            uow=uow,
            storage=storage,
            settings=settings,
            cipher=None,
        )

        assert resp.variant_type == "dark_shirt"
        assert resp.variant_status == "ready"
        assert resp.url == "https://storage.test/dark_shirt.png"

        # 2. List Variants
        variant_asset = MagicMock(spec=Asset)
        variant_asset.id = uuid.uuid4()
        variant_asset.workflow_id = workflow_id
        variant_asset.storage_key = "workflows/1/variants/1/dark.png"
        variant_asset.byte_size = 1234
        variant_asset.checksum_sha256 = "a" * 64
        variant_asset.width = 800
        variant_asset.height = 800
        variant_asset.has_alpha = True
        variant_asset.mime_type = "image/png"
        variant_asset.created_at = datetime.now(UTC)
        variant_asset.derived_from_id = master_id
        variant_asset.provenance = {
            "kind": "artwork_variant",
            "variant_type": "dark_shirt",
            "variant_status": "ready",
            "title": "Dark Shirt Version",
        }
        variant_asset.quality_check = {"is_valid": True}

        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset, variant_asset])
        list_resp = await list_artwork_variants_endpoint(
            workflow_id=workflow_id,
            user=user,
            uow=uow,
            storage=storage,
            settings=settings,
        )

        assert len(list_resp) == 1
        assert list_resp[0].variant_type == "dark_shirt"


class TestCustomerPackageWithVariants:
    @pytest.mark.asyncio
    async def test_package_builder_includes_approved_variant(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        master_id = uuid.uuid4()
        variant_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.name = "Cute Sleeping Fox"

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.title = "Cute Sleeping Fox Clipart PNG"
        listing.version = 1

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.width = 800
        master_asset.height = 800
        master_asset.mime_type = "image/png"
        master_asset.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        master_asset.provenance = {"profile": "etsy-png-standard"}

        # Approved Variant
        approved_var = MagicMock(spec=Asset)
        approved_var.id = variant_id
        approved_var.workflow_id = workflow_id
        approved_var.storage_key = "workflows/wf/variants/var1/dark_shirt.png"
        approved_var.mime_type = "image/png"
        approved_var.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        approved_var.provenance = {
            "kind": "artwork_variant",
            "variant_type": "dark_shirt",
            "variant_status": VariantStatus.APPROVED.value,
        }

        # Unapproved Variant (should NOT be included in ZIP)
        unapproved_var = MagicMock(spec=Asset)
        unapproved_var.id = uuid.uuid4()
        unapproved_var.workflow_id = workflow_id
        unapproved_var.storage_key = "workflows/wf/variants/var2/light_shirt.png"
        unapproved_var.mime_type = "image/png"
        unapproved_var.created_at = datetime(2026, 1, 3, tzinfo=UTC)
        unapproved_var.provenance = {
            "kind": "artwork_variant",
            "variant_type": "light_shirt",
            "variant_status": VariantStatus.READY.value,
        }

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.update = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.get = AsyncMock(return_value=master_asset)
        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset, approved_var, unapproved_var])
        uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
        uow.assets.add = AsyncMock()
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=None)
        uow.owner_settings.get_for_user = AsyncMock(return_value=None)

        storage = MagicMock()
        valid_png = _create_sample_master_png()
        storage.get = AsyncMock(return_value=valid_png)
        storage.put = AsyncMock(return_value=MagicMock(storage_key="workflows/wf/packages/pkg.zip"))

        service = CustomerPackageService(storage)
        package_asset = await service.build_customer_package(workflow_id, uow)

        assert package_asset is not None
        prov = package_asset.provenance or {}
        assert prov.get("variant_count") == 1
