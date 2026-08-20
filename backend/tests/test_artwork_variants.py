"""Unit and integration tests for Dark-Shirt / Light-Shirt Color Variant Generation."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

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
    VariantStatus,
    VariantType,
    build_variant_prompt,
    compute_variant_filename,
    filter_workflow_artwork_variants,
    is_valid_artwork_variant_asset,
    sanitize_hex_color,
)
from app.infrastructure.models import Asset, ListingDraft, ProductWorkflow, User
from app.ports.providers import ImageCandidate, ImageResponse
from app.providers.fake import FakeImageProvider


class TestArtworkVariantsDomain:
    def test_sanitize_hex_color(self) -> None:
        assert sanitize_hex_color("#FF5733") == "#FF5733"
        assert sanitize_hex_color("FF5733") == "#FF5733"
        assert sanitize_hex_color("#fff") == "#FFF"
        assert sanitize_hex_color("invalid") == "#FFFFFF"
        assert sanitize_hex_color(None) == "#FFFFFF"

    def test_build_variant_prompt_dark_shirt(self) -> None:
        pos, neg, version = build_variant_prompt(
            VariantType.DARK_SHIRT,
            original_positive_prompt="A cozy sleeping fox on transparent background",
        )
        assert "dark-colored apparel and black t-shirts" in pos
        assert "warm cream" in pos or "#F5E6C8" in pos
        assert "transparent background" in pos
        assert "black background" in neg
        assert version == "color-variant-v1"

    def test_build_variant_prompt_light_shirt(self) -> None:
        pos, neg, version = build_variant_prompt(
            VariantType.LIGHT_SHIRT,
            original_positive_prompt="A cozy sleeping fox on transparent background",
        )
        assert "light-colored apparel and white t-shirts" in pos
        assert "dark charcoal" in pos or "#1A1A1A" in pos
        assert "transparent background" in pos
        assert "white background" in neg

    def test_build_variant_prompt_custom_color(self) -> None:
        pos, neg, version = build_variant_prompt(
            VariantType.CUSTOM,
            custom_color="#E85D04",
            original_positive_prompt="Vintage sunset graphic",
        )
        assert "#E85D04" in pos
        assert "custom accent color" in pos

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


class TestArtworkVariantService:
    @pytest.mark.asyncio
    async def test_generate_variant_creates_derived_asset(self) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        master_asset_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_asset_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.width = 4500
        master_asset.height = 5400
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
        storage.get = AsyncMock(return_value=b"\x89PNG\r\n\x1a\nfake-master-bytes")
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

        master_asset = MagicMock(spec=Asset)
        master_asset.id = master_id
        master_asset.workflow_id = workflow_id
        master_asset.storage_key = "production/wf/master.png"
        master_asset.width = 4500
        master_asset.height = 5400
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
        storage.get = AsyncMock(return_value=b"\x89PNG\r\n\x1a\nmaster-bytes")
        storage.put = AsyncMock(return_value=MagicMock(storage_key=f"workflows/{workflow_id}/variants/1/dark_shirt.png"))
        storage.signed_url = AsyncMock(return_value="https://storage.test/dark_shirt.png")

        settings = MagicMock()
        settings.provider_mode = "fake"

        # 1. Create Variant
        req = CreateArtworkVariantRequest(variant_type="dark_shirt")
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
        variant_asset.width = 4500
        variant_asset.height = 5400
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
        master_asset.width = 4500
        master_asset.height = 5400
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
        # Return 1x1 valid PNG bytes
        valid_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa745a\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        storage.get = AsyncMock(return_value=valid_png)
        storage.put = AsyncMock(return_value=MagicMock(storage_key="workflows/wf/packages/pkg.zip"))

        service = CustomerPackageService(storage)
        package_asset = await service.build_customer_package(workflow_id, uow)

        assert package_asset is not None
        prov = package_asset.provenance or {}
        assert prov.get("variant_count") == 1
