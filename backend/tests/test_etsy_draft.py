"""Tests for Etsy draft listing creation, mockups upload, and ZIP dispatch application service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.etsy_draft import (
    execute_etsy_draft_pipeline,
    validate_pre_dispatch,
)
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.domain.errors import DomainError
from app.domain.workflow import RunStatus
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
    ShopConnection,
)
from app.infrastructure.security import CredentialCipher
from app.ports.providers import ObjectStorage
from app.ports.telegram import TelegramGateway
from app.providers.fake import FakeEtsyProvider


@pytest.fixture
def cipher() -> CredentialCipher:
    return CredentialCipher("test-encryption-key-32-chars-long!", key_version=1)


@pytest.fixture
def mock_storage() -> MagicMock:
    storage = MagicMock(spec=ObjectStorage)
    storage.get = AsyncMock(return_value=b"mock-binary-content-bytes")
    storage.put = AsyncMock()
    return storage


class TestEtsyDraftPreDispatch:
    @pytest.mark.asyncio
    async def test_validate_pre_dispatch_fails_if_workflow_wrong_state(
        self,
        mock_storage: MagicMock,
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.LISTING_REVIEW  # Not Gate 3 approved yet

        uow.workflows.get = AsyncMock(return_value=workflow)
        fake_etsy = FakeEtsyProvider()

        with pytest.raises(DomainError, match="must be 'READY_FOR_ETSY_DRAFT'"):
            await validate_pre_dispatch(
                workflow_id=workflow_id,
                owner_id=owner_id,
                uow=uow,
                storage=mock_storage,
                etsy_gateway=fake_etsy,
            )

    @pytest.mark.asyncio
    async def test_validate_pre_dispatch_fails_if_no_etsy_connection(
        self,
        mock_storage: MagicMock,
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.READY_FOR_ETSY_DRAFT

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=None)
        fake_etsy = FakeEtsyProvider()

        with pytest.raises(DomainError, match="No active Etsy shop connection found"):
            await validate_pre_dispatch(
                workflow_id=workflow_id,
                owner_id=owner_id,
                uow=uow,
                storage=mock_storage,
                etsy_gateway=fake_etsy,
            )


class TestEtsyDraftExecution:
    @pytest.mark.asyncio
    async def test_execute_etsy_draft_pipeline_happy_path(
        self,
        cipher: CredentialCipher,
        mock_storage: MagicMock,
    ) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        uow = MagicMock()
        uow.commit = AsyncMock()
        uow.audit = MagicMock()
        uow.audit.record = AsyncMock()

        # Workflow in READY_FOR_ETSY_DRAFT
        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.name = "Vintage Celestial Moon PNG"
        workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
        workflow.version = 1
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.workflows.transition = AsyncMock()

        # Connected Shop
        conn = MagicMock(spec=ShopConnection)
        conn.id = uuid.uuid4()
        conn.user_id = owner_id
        conn.etsy_shop_id = "shop_1234"
        conn.etsy_shop_name = "CelestialPrintsStudio"
        conn.connection_status = "connected"
        conn.is_connected = True
        conn.key_version = cipher.key_version
        conn.ciphertext_access_token = cipher.encrypt("valid_access_token_123")
        conn.ciphertext_refresh_token = cipher.encrypt("valid_refresh_token_123")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=2)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.telegram_connections.get_by_user_id = AsyncMock(return_value=None)

        # 13 Valid Etsy tags
        valid_tags = [
            "celestial png", "moon sublimation", "vintage moon", "mystic graphic",
            "witchy vibes", "astronomy clipart", "digital download", "shirt design",
            "printable art", "tshirt transfer", "cricut craft", "boho astronomy",
            "aesthetic moon"
        ]

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.title = "Vintage Celestial Moon PNG Sublimation Design"
        listing.description = "High quality transparent 300 DPI PNG download."
        listing.tags = valid_tags
        listing.price_minor_units = 499
        listing.currency = "USD"
        listing.taxonomy_id = 1049
        listing.etsy_listing_id = None
        listing.etsy_image_ids = []
        listing.etsy_file_id = None
        listing.etsy_dispatch_status = "not_started"

        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.update = AsyncMock(return_value=listing)
        uow.listing_drafts.update_etsy_draft = AsyncMock(return_value=listing)
        uow.listing_drafts.update_etsy_dispatch_status = AsyncMock(return_value=listing)
        uow.listing_drafts.record_etsy_image_upload = AsyncMock(return_value=listing)
        uow.listing_drafts.record_etsy_file_upload = AsyncMock(return_value=listing)

        now = datetime.now(UTC)
        # Assets: Master PNG + 2 User Mockups + 1 ZIP Package
        master_asset = MagicMock(spec=Asset)
        master_asset.id = uuid.uuid4()
        master_asset.workflow_id = workflow_id
        master_asset.mime_type = "image/png"
        master_asset.storage_key = f"workflows/{workflow_id}/master.png"
        master_asset.created_at = now
        master_asset.provenance = {"profile": "etsy-png-standard"}

        mockup_asset_1 = MagicMock(spec=Asset)
        mockup_asset_1.id = uuid.uuid4()
        mockup_asset_1.workflow_id = workflow_id
        mockup_asset_1.mime_type = "image/jpeg"
        mockup_asset_1.derived_from_id = master_asset.id
        mockup_asset_1.storage_key = f"workflows/{workflow_id}/mockups/tshirt.jpg"
        mockup_asset_1.created_at = now + timedelta(seconds=1)
        mockup_asset_1.provenance = {
            "asset_type": "mockup",
            "source": "user_template",
            "template_id": "tpl_1",
            "product_type": "tshirt",
            "is_cover": True,
            "listing_order": 1,
        }

        mockup_asset_2 = MagicMock(spec=Asset)
        mockup_asset_2.id = uuid.uuid4()
        mockup_asset_2.workflow_id = workflow_id
        mockup_asset_2.mime_type = "image/jpeg"
        mockup_asset_2.derived_from_id = master_asset.id
        mockup_asset_2.storage_key = f"workflows/{workflow_id}/mockups/mug.jpg"
        mockup_asset_2.created_at = now + timedelta(seconds=2)
        mockup_asset_2.provenance = {
            "asset_type": "mockup",
            "source": "user_template",
            "template_id": "tpl_2",
            "product_type": "mug",
            "is_cover": False,
            "listing_order": 2,
        }

        zip_asset = MagicMock(spec=Asset)
        zip_asset.id = uuid.uuid4()
        zip_asset.workflow_id = workflow_id
        zip_asset.mime_type = "application/zip"
        zip_asset.storage_key = f"workflows/{workflow_id}/packages/customer-package.zip"
        zip_asset.created_at = now + timedelta(seconds=3)
        zip_asset.provenance = {"kind": "customer_package"}

        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset, mockup_asset_1, mockup_asset_2, zip_asset])
        uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
        uow.assets.add = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])

        # Fake Etsy & Telegram Gateways
        fake_etsy = FakeEtsyProvider()
        fake_tg = MagicMock(spec=TelegramGateway)
        fake_tg.send_message = AsyncMock()

        result = await execute_etsy_draft_pipeline(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            storage=mock_storage,
            cipher=cipher,
            etsy_gateway=fake_etsy,
            telegram_gateway=fake_tg,
        )

        assert result is not None
        # Verify Etsy Listing was created in draft state
        assert len(fake_etsy.created_listings) == 1
        created = fake_etsy.created_listings[0]
        assert created["state"] == "draft"  # Strict draft guarantee
        assert created["shop_id"] == "shop_1234"

        # Verify Images were uploaded
        assert len(fake_etsy.uploaded_images) == 2

        # Verify ZIP was uploaded
        assert len(fake_etsy.uploaded_files) == 1

        # Verify state transition
        uow.workflows.transition.assert_called_once()
        assert uow.workflows.transition.call_args[1]["to_state"] == RunStatus.ETSY_DRAFT_CREATED

        # Verify Audit
        assert uow.audit.record.called

    @pytest.mark.asyncio
    async def test_execute_etsy_draft_splits_multi_files_when_package_exceeds_limit(
        self,
        cipher: CredentialCipher,
    ) -> None:
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        uow = MagicMock()
        uow.commit = AsyncMock()
        uow.audit = MagicMock()
        uow.audit.record = AsyncMock()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.name = "Huge Celestial Art PNG"
        workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
        workflow.version = 1
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.workflows.transition = AsyncMock()

        conn = MagicMock(spec=ShopConnection)
        conn.user_id = owner_id
        conn.etsy_shop_id = "shop_1234"
        conn.etsy_shop_name = "CelestialPrintsStudio"
        conn.is_connected = True
        conn.key_version = cipher.key_version
        conn.ciphertext_access_token = cipher.encrypt("valid_access_token_123")
        conn.ciphertext_refresh_token = cipher.encrypt("valid_refresh_token_123")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=2)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.telegram_connections.get_by_user_id = AsyncMock(return_value=None)

        valid_tags = [f"tag_{i}" for i in range(13)]
        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.title = "Huge Celestial Art PNG Sublimation"
        listing.description = "Transparent PNG."
        listing.tags = valid_tags
        listing.price_minor_units = 499
        listing.currency = "USD"
        listing.taxonomy_id = 6844
        listing.taxonomy_path = "Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files"
        listing.etsy_listing_id = None
        listing.etsy_image_ids = []
        listing.etsy_file_id = None
        listing.etsy_file_ids = []
        listing.etsy_dispatch_status = "not_started"

        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.update = AsyncMock(return_value=listing)
        uow.listing_drafts.update_etsy_draft = AsyncMock(return_value=listing)
        uow.listing_drafts.update_etsy_dispatch_status = AsyncMock(return_value=listing)
        uow.listing_drafts.record_etsy_image_upload = AsyncMock(return_value=listing)
        uow.listing_drafts.record_etsy_file_upload = AsyncMock(return_value=listing)

        # Storage mock with master PNG (5MB) and oversized delivery ZIP (25MB)
        master_bytes = b"M" * (5 * 1024 * 1024)
        mock_storage = MagicMock(spec=ObjectStorage)

        async def fake_storage_get(key: str) -> bytes:
            if "master.png" in key:
                return master_bytes
            if "mockup" in key:
                return b"mockup-bytes"
            # Simulate 25MB delivery zip
            return b"Z" * (25 * 1024 * 1024)

        mock_storage.get = AsyncMock(side_effect=fake_storage_get)
        mock_storage.put = AsyncMock(return_value=MagicMock(storage_key="workflows/pkg.zip"))

        master_asset = MagicMock(spec=Asset)
        master_asset.id = uuid.uuid4()
        master_asset.workflow_id = workflow_id
        master_asset.mime_type = "image/png"
        master_asset.storage_key = f"workflows/{workflow_id}/master.png"
        master_asset.width = 4500
        master_asset.height = 5400
        master_asset.checksum_sha256 = "dummy_sha256"
        master_asset.provenance = {"profile": "etsy-png-standard"}

        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset])
        uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
        uow.assets.add = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])

        fake_etsy = FakeEtsyProvider()

        await execute_etsy_draft_pipeline(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            storage=mock_storage,
            cipher=cipher,
            etsy_gateway=fake_etsy,
        )

        # Multiple digital files uploaded directly to Etsy (Master PNG + Print PDF + License & Info ZIP)
        assert len(fake_etsy.uploaded_files) >= 2
        uploaded_names = [f["filename"] for f in fake_etsy.uploaded_files]
        # Never upload Digital_Download_Access_Instructions.pdf!
        assert "Digital_Download_Access_Instructions.pdf" not in uploaded_names
        # Must contain actual master PNG artwork deliverable
        assert any("master.png" in fn for fn in uploaded_names)
        assert any("license-and-info.zip" in fn for fn in uploaded_names)
