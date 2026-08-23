"""Unit, integration, and regression tests for Deterministic Artwork Color Variant Engine and Quality Validation."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image, ImageDraw

from app.api.routes.artwork_variants import (
    create_artwork_variant_endpoint,
    list_artwork_variants_endpoint,
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
from app.infrastructure.models import Asset, ListingDraft, ProductWorkflow
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
        assert (
            is_valid_artwork_variant_asset(
                {"kind": "artwork_variant", "variant_type": "dark_shirt"}
            )
            is True
        )
        assert is_valid_artwork_variant_asset({"kind": "customer_package"}) is False
        assert is_valid_artwork_variant_asset({"asset_type": "mockup"}) is False
        assert is_valid_artwork_variant_asset(None) is False

    def test_compute_variant_filename(self) -> None:
        assert (
            compute_variant_filename("Shop_Fox", VariantType.DARK_SHIRT)
            == "Shop_Fox_Dark_Shirt.png"
        )
        assert (
            compute_variant_filename("Shop_Fox", VariantType.LIGHT_SHIRT)
            == "Shop_Fox_Light_Shirt.png"
        )
        assert (
            compute_variant_filename("Shop_Fox", VariantType.CUSTOM, "#E85D04")
            == "Shop_Fox_Custom_E85D04.png"
        )
        assert compute_variant_filename("Shop_Fox", "original") == "Shop_Fox_Original.png"

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
        assert charcoal_pixel[0] < 60
        assert charcoal_pixel[1] < 60
        assert charcoal_pixel[2] < 60
        assert charcoal_pixel[3] == 255

    def test_recolor_custom_hex_recolors_target_tone(self) -> None:
        master_bytes = _create_sample_master_png()
        variant_bytes, report = recolor_artwork_variant(
            source_bytes=master_bytes,
            variant_type=VariantType.CUSTOM,
            target_color_hex="#E85D04",
        )

        out_img = Image.open(io.BytesIO(variant_bytes))
        custom_pixel = out_img.getpixel((100, 100))
        assert custom_pixel[0] > 200  # Red
        assert custom_pixel[1] > 70  # Green
        assert custom_pixel[2] < 30  # Blue
        assert custom_pixel[3] == 255


class TestVariantValidationGuards:
    def test_reject_jpeg_format_with_explicit_error(self) -> None:
        master_bytes = _create_sample_master_png()
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"

        with pytest.raises(
            ArtworkVariantValidationError,
            match="Variant provider returned JPEG. Transparent PNG required.",
        ):
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

        with pytest.raises(
            ArtworkVariantValidationError, match="Generated variant lacks transparency"
        ):
            validate_artwork_variant(
                source_bytes=master_bytes,
                variant_bytes=opaque_png_bytes,
                variant_type=VariantType.DARK_SHIRT,
            )

    def test_validation_flags_baked_checkerboard(self) -> None:
        # Create an image with baked gray/white checkerboard in corner
        w, h = 800, 800
        img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw alternating gray/white 10x10 squares in corner (0,0) to (100,100)
        for y in range(0, 100, 10):
            for x in range(0, 100, 10):
                color = (
                    (204, 204, 204, 255) if ((x // 10 + y // 10) % 2 == 0) else (255, 255, 255, 255)
                )
                draw.rectangle([x, y, x + 9, y + 9], fill=color)

        assert detect_baked_checkerboard(img) is True

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        checker_bytes = buf.getvalue()

        master_bytes = _create_sample_master_png()
        with pytest.raises(
            ArtworkVariantValidationError, match="Detected baked checkerboard pattern"
        ):
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
        uow.assets.add = AsyncMock()
        uow.commit = AsyncMock()

        storage = MagicMock()
        storage.get = AsyncMock(return_value=master_bytes)
        storage.put = AsyncMock(
            return_value=MagicMock(storage_key="workflows/1/variants/1/dark_shirt.png")
        )

        service = ArtworkVariantService(storage, FakeImageProvider())
        asset = await service.generate_variant(
            workflow_id=workflow_id,
            owner_id=owner_id,
            variant_type=VariantType.DARK_SHIRT,
            uow=uow,
        )

        assert asset.derived_from_id == master_asset_id
        assert asset.has_alpha is True
        assert asset.provenance["variant_type"] == "dark_shirt"
        assert asset.provenance["variant_status"] == VariantStatus.READY.value

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
        variant_asset.provenance = {
            "kind": "artwork_variant",
            "variant_type": "dark_shirt",
            "variant_status": VariantStatus.READY.value,
        }

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.assets.get = AsyncMock(return_value=variant_asset)
        uow.commit = AsyncMock()

        service = ArtworkVariantService(MagicMock(), FakeImageProvider())

        # 1. Approve
        approved = await service.approve_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=owner_id,
            uow=uow,
        )
        assert approved.provenance["variant_status"] == VariantStatus.APPROVED.value

        # 2. Reject
        rejected = await service.reject_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=owner_id,
            uow=uow,
        )
        assert rejected.provenance["variant_status"] == VariantStatus.REJECTED.value

    @pytest.mark.asyncio
    async def test_update_variant_package_inclusion(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        master_id = uuid.uuid4()
        variant_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.provenance = {"profile": "etsy-png-standard"}
        master_asset.created_at = datetime(2026, 1, 1, tzinfo=UTC)

        variant_asset = MagicMock(spec=Asset)
        variant_asset.id = variant_id
        variant_asset.workflow_id = workflow_id
        variant_asset.storage_key = "workflows/wf/variants/var1/dark_shirt.png"
        variant_asset.derived_from_id = master_id
        variant_asset.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        variant_asset.provenance = {
            "kind": "artwork_variant",
            "variant_type": "dark_shirt",
            "variant_status": VariantStatus.READY.value,  # Not approved yet!
        }

        async def _mock_get_asset(aid: uuid.UUID) -> Asset | None:
            if aid == master_id:
                return master_asset
            if aid == variant_id:
                return variant_asset
            return None

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.get = AsyncMock(side_effect=_mock_get_asset)
        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset, variant_asset])
        uow.commit = AsyncMock()

        service = ArtworkVariantService(MagicMock(), FakeImageProvider())

        # Fails if unapproved
        with pytest.raises(ArtworkVariantError, match="Only approved variants can be included"):
            await service.update_variant_package_inclusion(
                workflow_id=workflow_id,
                asset_id=variant_id,
                include_in_buyer_package=True,
                owner_id=owner_id,
                uow=uow,
            )

        # Set approved
        variant_asset.provenance["variant_status"] = VariantStatus.APPROVED.value
        updated = await service.update_variant_package_inclusion(
            workflow_id=workflow_id,
            asset_id=variant_id,
            include_in_buyer_package=True,
            owner_id=owner_id,
            uow=uow,
        )
        assert updated.provenance["include_in_buyer_package"] is True

        # Fails if outdated (derived from older master)
        variant_asset.derived_from_id = uuid.uuid4()
        with pytest.raises(ArtworkVariantError, match="generated from an older master artwork"):
            await service.update_variant_package_inclusion(
                workflow_id=workflow_id,
                asset_id=variant_id,
                include_in_buyer_package=True,
                owner_id=owner_id,
                uow=uow,
            )


class TestArtworkVariantRoutes:
    @pytest.mark.asyncio
    async def test_create_and_list_endpoints(self) -> None:
        from app.api.routes.artwork_variants import (
            update_artwork_variant_package_endpoint,
        )
        from app.api.schemas import UpdateArtworkVariantPackageRequest

        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        master_id = uuid.uuid4()
        variant_id = uuid.uuid4()

        user = MagicMock()
        user.id = owner_id

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.width = 800
        master_asset.height = 800
        master_asset.mime_type = "image/png"
        master_asset.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        master_asset.provenance = {"profile": "etsy-png-standard"}

        variant_asset = MagicMock(spec=Asset)
        variant_asset.id = variant_id
        variant_asset.workflow_id = workflow_id
        variant_asset.storage_key = "workflows/1/variants/1/dark.png"
        variant_asset.byte_size = 1234
        variant_asset.checksum_sha256 = "a" * 64
        variant_asset.width = 800
        variant_asset.height = 800
        variant_asset.has_alpha = True
        variant_asset.mime_type = "image/png"
        variant_asset.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        variant_asset.derived_from_id = master_id
        variant_asset.provenance = {
            "kind": "artwork_variant",
            "variant_type": "dark_shirt",
            "variant_status": "ready",
            "title": "Dark Shirt Version",
        }
        variant_asset.quality_check = {"is_valid": True}

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.get = AsyncMock(return_value=master_asset)
        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset, variant_asset])
        uow.assets.add = AsyncMock()
        uow.commit = AsyncMock()

        storage = MagicMock()
        sample_master = _create_sample_master_png()
        storage.get = AsyncMock(return_value=sample_master)
        storage.put = AsyncMock(
            return_value=MagicMock(storage_key="workflows/1/variants/1/dark.png")
        )
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
        list_resp = await list_artwork_variants_endpoint(
            workflow_id=workflow_id,
            user=user,
            uow=uow,
            storage=storage,
            settings=settings,
        )

        assert len(list_resp) == 1
        assert list_resp[0].variant_type == "dark_shirt"

        # 3. Patch Package Inclusion Endpoint
        variant_asset.provenance["variant_status"] = VariantStatus.APPROVED.value
        uow.assets.get = AsyncMock(return_value=variant_asset)

        patch_req = UpdateArtworkVariantPackageRequest(include_in_buyer_package=True)
        patch_resp = await update_artwork_variant_package_endpoint(
            workflow_id=workflow_id,
            variant_id=variant_id,
            payload=patch_req,
            user=user,
            uow=uow,
            storage=storage,
        )
        assert patch_resp.include_in_buyer_package is True


class TestCustomerPackageWithVariants:
    @pytest.mark.asyncio
    async def test_package_builder_includes_only_selected_approved_variants(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        master_id = uuid.uuid4()
        selected_var_id = uuid.uuid4()
        unselected_var_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.name = "Cute Sleeping Fox"

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.title = "Cute Sleeping Fox Clipart PNG"
        listing.version = 1
        listing.etsy_dispatch_status = "not_started"
        listing.etsy_listing_id = None
        listing.etsy_properties = {}

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.width = 800
        master_asset.height = 800
        master_asset.mime_type = "image/png"
        master_asset.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        master_asset.provenance = {"profile": "etsy-png-standard"}

        # 1. Approved Variant SELECTED for Buyer Package
        selected_var = MagicMock(spec=Asset)
        selected_var.id = selected_var_id
        selected_var.workflow_id = workflow_id
        selected_var.derived_from_id = master_id
        selected_var.storage_key = "workflows/wf/variants/var1/dark_shirt.png"
        selected_var.mime_type = "image/png"
        selected_var.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        selected_var.provenance = {
            "kind": "artwork_variant",
            "variant_type": "dark_shirt",
            "variant_status": VariantStatus.APPROVED.value,
            "include_in_buyer_package": True,
            "title": "Dark Shirt Version",
        }

        # 2. Approved Variant UNSELECTED (should NOT be included)
        unselected_var = MagicMock(spec=Asset)
        unselected_var.id = unselected_var_id
        unselected_var.workflow_id = workflow_id
        unselected_var.derived_from_id = master_id
        unselected_var.storage_key = "workflows/wf/variants/var2/light_shirt.png"
        unselected_var.mime_type = "image/png"
        unselected_var.created_at = datetime(2026, 1, 3, tzinfo=UTC)
        unselected_var.provenance = {
            "kind": "artwork_variant",
            "variant_type": "light_shirt",
            "variant_status": VariantStatus.APPROVED.value,
            "include_in_buyer_package": False,
            "title": "Light Shirt Version",
        }

        # 3. Unapproved Variant (should NOT be included)
        unapproved_var = MagicMock(spec=Asset)
        unapproved_var.id = uuid.uuid4()
        unapproved_var.workflow_id = workflow_id
        unapproved_var.derived_from_id = master_id
        unapproved_var.storage_key = "workflows/wf/variants/var3/custom.png"
        unapproved_var.mime_type = "image/png"
        unapproved_var.created_at = datetime(2026, 1, 4, tzinfo=UTC)
        unapproved_var.provenance = {
            "kind": "artwork_variant",
            "variant_type": "custom",
            "variant_status": VariantStatus.READY.value,
            "include_in_buyer_package": True,  # Unapproved so must be ignored!
        }

        # 4. Outdated Variant (should NOT be included)
        outdated_var = MagicMock(spec=Asset)
        outdated_var.id = uuid.uuid4()
        outdated_var.workflow_id = workflow_id
        outdated_var.derived_from_id = uuid.uuid4()  # Mismatched older master!
        outdated_var.storage_key = "workflows/wf/variants/var4/dark_old.png"
        outdated_var.mime_type = "image/png"
        outdated_var.created_at = datetime(2026, 1, 5, tzinfo=UTC)
        outdated_var.provenance = {
            "kind": "artwork_variant",
            "variant_type": "dark_shirt",
            "variant_status": VariantStatus.APPROVED.value,
            "include_in_buyer_package": True,
        }

        all_assets = [master_asset, selected_var, unselected_var, unapproved_var, outdated_var]

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.update = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.get = AsyncMock(return_value=master_asset)
        uow.assets.list_for_workflow = AsyncMock(return_value=all_assets)
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

        manifest = prov.get("manifest") or {}
        files = manifest.get("files") or []
        file_types = [f["type"] for f in files]
        assert "original" in file_types
        assert "dark_shirt" in file_types
        assert "light_shirt" not in file_types
        assert "custom" not in file_types

        # Check preview after package is built
        all_assets.append(package_asset)
        preview = await service.get_package_preview(workflow_id, uow)
        assert preview["included_count"] == 2  # Original master + 1 selected variant
        assert preview["needs_rebuild"] is False
