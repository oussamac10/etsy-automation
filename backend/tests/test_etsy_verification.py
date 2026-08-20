"""Comprehensive unit tests for Post-Dispatch Etsy Draft Verification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.etsy_verification import verify_etsy_draft_listing
from app.domain.enums import AuditAction
from app.domain.etsy_verification import (
    EtsyDraftVerification,
    EtsyOverallVerificationStatus,
    EtsyVerificationCheckStatus,
    compare_etsy_draft,
)
from app.domain.workflow import RunStatus
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
    ShopConnection,
)
from app.infrastructure.security import CredentialCipher
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import (
    EtsyFileResponse,
    EtsyImageResponse,
    EtsyListingResponse,
)
from app.providers.fake import FakeEtsyProvider


@pytest.fixture
def cipher() -> CredentialCipher:
    return CredentialCipher("test-encryption-key-32-chars-long!", key_version=1)


class TestEtsyDraftVerificationComparison:
    """Test pure domain comparison between local listing draft expectations and remote Etsy payloads."""

    def test_complete_synced_draft(self) -> None:
        """All verifiable fields match exactly between local state and Etsy API response."""
        res = compare_etsy_draft(
            workflow_id="wf-101",
            listing_id="4559404921",
            expected_title="Cozy Fall Book Lover PNG Sublimation Design",
            expected_description="High resolution 300 DPI PNG file for t-shirt printing.",
            expected_tags=["cozy fall", "book lover", "sublimation png", "autumn art", "reading gift"],
            expected_price_minor=499,
            expected_currency="EUR",
            expected_quantity=999,
            expected_sku="NCP-COZY-FALL-6125",
            expected_taxonomy_id=77,
            expected_taxonomy_path="Art & Collectibles > Drawing & Illustration > Digital",
            expected_shop_section_id="101",
            expected_shop_section_name="Fall PNGs",
            expected_should_auto_renew=False,
            expected_properties={"148789511893": ["Canvas"]},
            expected_mockup_count=4,
            expected_file_count=2,
            expected_filenames=["cozy_fall_master.png", "cozy_fall_extras.zip"],
            expected_ai_disclosure="Artwork generated with AI assistance.",
            expected_shopping_cart_summary="Cozy fall book lover PNG digital download",
            actual_listing={
                "listing_id": 4559404921,
                "state": "draft",
                "title": "Cozy Fall Book Lover PNG Sublimation Design",
                "description": "High resolution 300 DPI PNG file for t-shirt printing.",
                "tags": ["cozy fall", "book lover", "sublimation png", "autumn art", "reading gift"],
                "price": {"amount": 499, "divisor": 100, "currency_code": "EUR"},
                "quantity": 999,
                "sku": "NCP-COZY-FALL-6125",
                "taxonomy_id": 77,
                "shop_section_id": 101,
                "should_auto_renew": False,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "listing_type": "download",
                "is_supply": False,
            },
            actual_inventory={
                "products": [
                    {
                        "product_id": 1,
                        "sku": "NCP-COZY-FALL-6125",
                        "offerings": [{"price": {"amount": 499, "divisor": 100, "currency_code": "EUR"}, "quantity": 999}],
                    }
                ]
            },
            actual_images=[{"listing_image_id": f"img-{i}", "rank": i} for i in range(1, 5)],
            actual_files=[
                {"listing_file_id": "f-1", "filename": "cozy_fall_master.png", "rank": 1},
                {"listing_file_id": "f-2", "filename": "cozy_fall_extras.zip", "rank": 2},
            ],
            actual_properties=[{"property_id": 148789511893, "values": ["Canvas"]}],
        )

        assert res.status == EtsyOverallVerificationStatus.VERIFIED
        assert res.summary.synced >= 10
        assert res.summary.warnings == 0
        assert res.summary.errors == 0
        assert res.summary.manual_review == 3  # ai_disclosure, shopping_cart_summary, thumbnail_crop

    def test_title_and_description_mismatch(self) -> None:
        """Title and description differences are flagged as 'different'."""
        res = compare_etsy_draft(
            workflow_id="wf-101",
            listing_id="4559404921",
            expected_title="Expected Local Title",
            expected_description="Local Description",
            expected_tags=["tag1"],
            expected_price_minor=499,
            expected_currency="USD",
            expected_quantity=999,
            expected_sku="SKU-1",
            expected_taxonomy_id=77,
            expected_taxonomy_path="Digital",
            expected_shop_section_id=None,
            expected_shop_section_name=None,
            expected_should_auto_renew=False,
            expected_properties={},
            expected_mockup_count=1,
            expected_file_count=1,
            expected_filenames=["file.zip"],
            expected_ai_disclosure=None,
            expected_shopping_cart_summary=None,
            actual_listing={
                "listing_id": 4559404921,
                "state": "draft",
                "title": "Different Remote Title on Etsy",
                "description": "Modified Etsy Description",
                "tags": ["tag1"],
                "price": {"amount": 499, "divisor": 100, "currency_code": "USD"},
                "quantity": 999,
                "sku": "SKU-1",
                "taxonomy_id": 77,
                "shop_section_id": None,
                "should_auto_renew": False,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "listing_type": "download",
                "is_supply": False,
            },
            actual_inventory={"products": [{"sku": "SKU-1", "offerings": [{"quantity": 999}]}]},
            actual_images=[{"listing_image_id": "img-1", "rank": 1}],
            actual_files=[{"listing_file_id": "f-1", "filename": "file.zip", "rank": 1}],
            actual_properties=[],
        )

        assert res.status == EtsyOverallVerificationStatus.NEEDS_ATTENTION
        assert res.summary.warnings >= 2

        title_check = next(c for c in res.checks if c.key == "title")
        assert title_check.status == EtsyVerificationCheckStatus.DIFFERENT
        assert title_check.expected == "Expected Local Title"
        assert title_check.actual == "Different Remote Title on Etsy"

        desc_check = next(c for c in res.checks if c.key == "description")
        assert desc_check.status == EtsyVerificationCheckStatus.DIFFERENT

    def test_tags_missing_and_unexpected(self) -> None:
        """Case-normalized tag diff correctly reports missing and unexpected tags."""
        res = compare_etsy_draft(
            workflow_id="wf-101",
            listing_id="4559404921",
            expected_title="Title",
            expected_description="Desc",
            expected_tags=["Cottagecore Art", "Mushroom PNG", "Sublimation Shirt"],
            expected_price_minor=499,
            expected_currency="USD",
            expected_quantity=999,
            expected_sku="SKU",
            expected_taxonomy_id=77,
            expected_taxonomy_path="Digital",
            expected_shop_section_id=None,
            expected_shop_section_name=None,
            expected_should_auto_renew=False,
            expected_properties={},
            expected_mockup_count=1,
            expected_file_count=1,
            expected_filenames=["file.zip"],
            expected_ai_disclosure=None,
            expected_shopping_cart_summary=None,
            actual_listing={
                "listing_id": 4559404921,
                "state": "draft",
                "title": "Title",
                "description": "Desc",
                "tags": ["cottagecore art", "Old Outdated Tag", "vintage graphic"],
                "price": {"amount": 499, "divisor": 100, "currency_code": "USD"},
                "quantity": 999,
                "sku": "SKU",
                "taxonomy_id": 77,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "listing_type": "download",
                "is_supply": False,
            },
            actual_inventory=None,
            actual_images=[{"listing_image_id": "img-1", "rank": 1}],
            actual_files=[{"listing_file_id": "f-1", "filename": "file.zip", "rank": 1}],
            actual_properties=[],
        )

        tags_check = next(c for c in res.checks if c.key == "tags")
        assert tags_check.status == EtsyVerificationCheckStatus.DIFFERENT
        assert "Mushroom PNG" in tags_check.details["missing"]
        assert "Sublimation Shirt" in tags_check.details["missing"]
        assert "Old Outdated Tag" in tags_check.details["unexpected"]

    def test_price_and_currency_mismatch(self) -> None:
        """Mismatch in minor units or currency code is caught."""
        res = compare_etsy_draft(
            workflow_id="wf-101",
            listing_id="4559404921",
            expected_title="Title",
            expected_description="Desc",
            expected_tags=["tag"],
            expected_price_minor=499,
            expected_currency="EUR",
            expected_quantity=999,
            expected_sku="SKU",
            expected_taxonomy_id=77,
            expected_taxonomy_path="Digital",
            expected_shop_section_id=None,
            expected_shop_section_name=None,
            expected_should_auto_renew=False,
            expected_properties={},
            expected_mockup_count=1,
            expected_file_count=1,
            expected_filenames=["file.zip"],
            expected_ai_disclosure=None,
            expected_shopping_cart_summary=None,
            actual_listing={
                "listing_id": 4559404921,
                "state": "draft",
                "title": "Title",
                "description": "Desc",
                "tags": ["tag"],
                "price": {"amount": 550, "divisor": 100, "currency_code": "USD"},
                "quantity": 999,
                "sku": "SKU",
                "taxonomy_id": 77,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "listing_type": "download",
                "is_supply": False,
            },
            actual_inventory=None,
            actual_images=[{"listing_image_id": "img-1", "rank": 1}],
            actual_files=[{"listing_file_id": "f-1", "filename": "file.zip", "rank": 1}],
            actual_properties=[],
        )

        price_check = next(c for c in res.checks if c.key == "price")
        assert price_check.status == EtsyVerificationCheckStatus.DIFFERENT
        assert "4.99 EUR" in price_check.expected
        assert "5.50 USD" in price_check.actual

    def test_missing_shop_section_on_etsy(self) -> None:
        """Expected shop section when Etsy shows None is reported as a warning."""
        res = compare_etsy_draft(
            workflow_id="wf-101",
            listing_id="4559404921",
            expected_title="Title",
            expected_description="Desc",
            expected_tags=["tag"],
            expected_price_minor=499,
            expected_currency="USD",
            expected_quantity=999,
            expected_sku="SKU",
            expected_taxonomy_id=77,
            expected_taxonomy_path="Digital",
            expected_shop_section_id="101",
            expected_shop_section_name="Fall PNGs",
            expected_should_auto_renew=False,
            expected_properties={},
            expected_mockup_count=1,
            expected_file_count=1,
            expected_filenames=["file.zip"],
            expected_ai_disclosure=None,
            expected_shopping_cart_summary=None,
            actual_listing={
                "listing_id": 4559404921,
                "state": "draft",
                "title": "Title",
                "description": "Desc",
                "tags": ["tag"],
                "price": {"amount": 499, "divisor": 100, "currency_code": "USD"},
                "quantity": 999,
                "sku": "SKU",
                "taxonomy_id": 77,
                "shop_section_id": None,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "listing_type": "download",
                "is_supply": False,
            },
            actual_inventory=None,
            actual_images=[{"listing_image_id": "img-1", "rank": 1}],
            actual_files=[{"listing_file_id": "f-1", "filename": "file.zip", "rank": 1}],
            actual_properties=[],
        )

        sec_check = next(c for c in res.checks if c.key == "shop_section")
        assert sec_check.status == EtsyVerificationCheckStatus.DIFFERENT
        assert "Fall PNGs" in sec_check.expected
        assert "None on Etsy" in sec_check.actual

    def test_missing_digital_file_reported(self) -> None:
        """If zero digital files exist on Etsy when files were expected, check reports MISSING."""
        res = compare_etsy_draft(
            workflow_id="wf-101",
            listing_id="4559404921",
            expected_title="Title",
            expected_description="Desc",
            expected_tags=["tag"],
            expected_price_minor=499,
            expected_currency="USD",
            expected_quantity=999,
            expected_sku="SKU",
            expected_taxonomy_id=77,
            expected_taxonomy_path="Digital",
            expected_shop_section_id=None,
            expected_shop_section_name=None,
            expected_should_auto_renew=False,
            expected_properties={},
            expected_mockup_count=2,
            expected_file_count=2,
            expected_filenames=["file1.zip", "file2.zip"],
            expected_ai_disclosure=None,
            expected_shopping_cart_summary=None,
            actual_listing={
                "listing_id": 4559404921,
                "state": "draft",
                "title": "Title",
                "description": "Desc",
                "tags": ["tag"],
                "price": {"amount": 499, "divisor": 100, "currency_code": "USD"},
                "quantity": 999,
                "sku": "SKU",
                "taxonomy_id": 77,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "listing_type": "download",
                "is_supply": False,
            },
            actual_inventory=None,
            actual_images=[{"listing_image_id": "img-1", "rank": 1}, {"listing_image_id": "img-2", "rank": 2}],
            actual_files=[],  # Missing files
            actual_properties=[],
        )

        files_check = next(c for c in res.checks if c.key == "digital_files")
        assert files_check.status == EtsyVerificationCheckStatus.MISSING
        assert res.status == EtsyOverallVerificationStatus.NEEDS_ATTENTION


class TestEtsyVerificationService:
    """Test verify_etsy_draft_listing application service end-to-end with fake provider."""

    @pytest.mark.asyncio
    async def test_successful_verification_persisted_and_audited(
        self, cipher: CredentialCipher
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        listing_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.ETSY_DRAFT_CREATED
        uow.workflows.get = AsyncMock(return_value=workflow)

        conn = MagicMock(spec=ShopConnection)
        conn.id = uuid.uuid4()
        conn.user_id = owner_id
        conn.shop_id = "12345"
        conn.shop_name = "NovaCraftPixel"
        conn.is_connected = True
        conn.connection_status = "connected"
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("valid-access-token")
        conn.ciphertext_refresh_token = cipher.encrypt("valid-refresh-token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=2)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.shop_connections.update_tokens = AsyncMock()

        listing = MagicMock(spec=ListingDraft)
        listing.id = listing_id
        listing.workflow_id = workflow_id
        listing.title = "Cozy Fall Book Lover PNG"
        listing.description = "Download file."
        listing.tags = ["cozy fall", "book lover"]
        listing.price_minor_units = 499
        listing.currency = "USD"
        listing.quantity = 999
        listing.sku = "NCP-COZY-FALL-6125"
        listing.taxonomy_id = 77
        listing.taxonomy_path = "Digital"
        listing.shop_section_id = None
        listing.shop_section_name = None
        listing.should_auto_renew = False
        listing.etsy_properties = {}
        listing.etsy_listing_id = "4559404921"
        listing.etsy_image_ids = ["img-1", "img-2"]
        listing.etsy_file_id = "f-1"
        listing.etsy_file_ids = ["f-1", "f-2"]
        listing.ai_disclosure = "AI generated artwork"
        listing.shopping_cart_summary = "Cozy fall book lover PNG"

        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.update_etsy_verification = AsyncMock(return_value=listing)
        uow.assets.list_for_workflow = AsyncMock(return_value=[])
        uow.audit.record = AsyncMock()
        uow.commit = AsyncMock()

        fake_etsy = FakeEtsyProvider()
        fake_etsy.created_listings.append(
            {
                "listing_id": "4559404921",
                "title": "Cozy Fall Book Lover PNG",
                "description": "Download file.",
                "tags": ["cozy fall", "book lover"],
                "price_cents": 499,
                "currency": "USD",
                "quantity": 999,
                "sku": "NCP-COZY-FALL-6125",
                "taxonomy_id": 77,
                "shop_section_id": None,
                "should_auto_renew": False,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "item_type": "download",
                "is_supply": False,
            }
        )
        fake_etsy.uploaded_images.extend(
            [
                {"listing_image_id": "img-1", "listing_id": "4559404921", "rank": 1},
                {"listing_image_id": "img-2", "listing_id": "4559404921", "rank": 2},
            ]
        )
        fake_etsy.uploaded_files.extend(
            [
                {"listing_file_id": "f-1", "listing_id": "4559404921", "filename": "package.zip", "rank": 1},
                {"listing_file_id": "f-2", "listing_id": "4559404921", "filename": "extras.zip", "rank": 2},
            ]
        )

        report = await verify_etsy_draft_listing(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            cipher=cipher,
            etsy_gateway=fake_etsy,
        )

        assert report.status == EtsyOverallVerificationStatus.VERIFIED
        assert report.listing_id == "4559404921"
        assert report.summary.synced >= 10
        assert report.summary.warnings == 0

        # Verify update_etsy_verification called
        uow.listing_drafts.update_etsy_verification.assert_awaited_once()
        # Verify audit recorded
        uow.audit.record.assert_awaited_once_with(
            action=AuditAction.ETSY_DRAFT_VERIFIED,
            entity_type="listing_draft",
            entity_id=listing_id,
            workflow_id=workflow_id,
            actor=str(owner_id),
            summary=f"Etsy draft verified ({report.status.value}): {report.summary.synced} synced, {report.summary.warnings} warnings, {report.summary.manual_review} manual checks.",
            metadata={
                "workflow_id": str(workflow_id),
                "listing_id": "4559404921",
                "status": "verified",
                "synced": report.summary.synced,
                "warnings": 0,
                "errors": 0,
                "manual_review": 3,
            },
        )

    @pytest.mark.asyncio
    async def test_auth_revocation_returns_failed_report_without_deleting_draft(
        self, cipher: CredentialCipher
    ) -> None:
        """Revoked token produces a clear error report and does not alter local draft state."""
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        uow.workflows.get = AsyncMock(return_value=workflow)

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.shop_id = "12345"
        conn.encrypted_access_token = cipher.encrypt("revoked-token")
        conn.encrypted_refresh_token = cipher.encrypt("revoked-token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=2)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.shop_connections.update_tokens = AsyncMock()

        listing = MagicMock(spec=ListingDraft)
        listing.etsy_listing_id = "4559404921"
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)

        fake_etsy = FakeEtsyProvider()
        fake_etsy.revoked_token = True

        report = await verify_etsy_draft_listing(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            cipher=cipher,
            etsy_gateway=fake_etsy,
        )

        assert report.status == EtsyOverallVerificationStatus.FAILED
        assert report.summary.errors >= 1
        assert "Etsy authorization" in report.error_message or "reconnect" in report.error_message.lower()
        # Verify local draft was NOT cleared or deleted
        uow.listing_drafts.clear_etsy_draft_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_etsy_404_triggers_reconciliation(
        self, cipher: CredentialCipher
    ) -> None:
        """Authoritative 404 from Etsy triggers reconciliation resetting workflow to READY_FOR_ETSY_DRAFT."""
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.version = 1
        workflow.state = RunStatus.ETSY_DRAFT_CREATED
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.workflows.transition = AsyncMock()

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.connection_status = "connected"
        conn.key_version = 1
        conn.shop_id = "12345"
        conn.ciphertext_access_token = cipher.encrypt("token")
        conn.ciphertext_refresh_token = cipher.encrypt("refresh")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=2)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.shop_connections.update_tokens = AsyncMock()

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.etsy_listing_id = "4559404921"
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.clear_etsy_draft_state = AsyncMock()
        uow.audit.record = AsyncMock()
        uow.commit = AsyncMock()

        fake_etsy = FakeEtsyProvider()
        fake_etsy.deleted_listing_ids.add("4559404921")

        report = await verify_etsy_draft_listing(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            cipher=cipher,
            etsy_gateway=fake_etsy,
        )

        assert report.status == EtsyOverallVerificationStatus.FAILED
        assert "404" in report.error_message
        # Verify reconciliation was invoked and cleared draft state
        uow.listing_drafts.clear_etsy_draft_state.assert_awaited_once()

    def test_materials_removed_on_etsy_reported_as_different(self) -> None:
        """When a material is removed on Etsy, verification reports 'different' with missing material item."""
        expected_properties = {
            "148789511893": {
                "property_id": 148789511893,
                "property_name": "Materials",
                "values": ["Canvas", "Paper"],
            }
        }
        res = compare_etsy_draft(
            workflow_id="wf-101",
            listing_id="4559404921",
            expected_title="Title",
            expected_description="Desc",
            expected_tags=["tag"],
            expected_price_minor=499,
            expected_currency="EUR",
            expected_quantity=999,
            expected_sku="SKU",
            expected_taxonomy_id=77,
            expected_taxonomy_path="Digital",
            expected_shop_section_id=None,
            expected_shop_section_name=None,
            expected_should_auto_renew=False,
            expected_properties=expected_properties,
            expected_mockup_count=1,
            expected_file_count=1,
            expected_filenames=["file.zip"],
            expected_ai_disclosure=None,
            expected_shopping_cart_summary=None,
            actual_listing={
                "listing_id": 4559404921,
                "state": "draft",
                "title": "Title",
                "description": "Desc",
                "tags": ["tag"],
                "price": {"amount": 499, "divisor": 100, "currency_code": "EUR"},
                "quantity": 999,
                "sku": "SKU",
                "taxonomy_id": 77,
                "who_made": "i_did",
                "when_made": "2020_2026",
                "listing_type": "download",
                "is_supply": False,
                "materials": ["Canvas"],  # User removed 'Paper' on Etsy
            },
            actual_inventory=None,
            actual_images=[{"listing_image_id": "img-1", "rank": 1}],
            actual_files=[{"listing_file_id": "f-1", "filename": "file.zip", "rank": 1}],
            actual_properties=[{"property_id": 148789511893, "property_name": "Materials", "values": ["Canvas"]}],
        )

        assert res.status == EtsyOverallVerificationStatus.NEEDS_ATTENTION
        attr_check = next(c for c in res.checks if c.key == "attributes")
        assert attr_check.status == EtsyVerificationCheckStatus.DIFFERENT
        assert "Paper" in attr_check.message
        prop_item = attr_check.details["properties"][0]
        assert prop_item["status"] == "different"
        assert prop_item["missing"] == ["Paper"]

