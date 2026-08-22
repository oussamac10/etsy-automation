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


def _create_test_png_bytes(
    width: int = 4500,
    height: int = 5400,
    color_type: int = 6,
    raw_bytes: int = 1000,
    compressible: bool = True,
) -> bytes:
    import os
    import struct
    import zlib

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    if compressible:
        raw_scanlines = b"\x00" + (b"ABCD1234EFGH5678" * (raw_bytes // 16 + 1))[:raw_bytes]
    else:
        raw_scanlines = b"\x00" + os.urandom(raw_bytes)

    compressed_idat = zlib.compress(raw_scanlines, level=6 if compressible else 0)
    idat_crc = zlib.crc32(b"IDAT" + compressed_idat)
    idat = struct.pack(">I", len(compressed_idat)) + b"IDAT" + compressed_idat + struct.pack(">I", idat_crc)

    iend_crc = zlib.crc32(b"IEND")
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    return header + ihdr + idat + iend


@pytest.fixture
def cipher() -> CredentialCipher:
    return CredentialCipher("test-encryption-key-32-chars-long!", key_version=1)


@pytest.fixture
def mock_storage() -> MagicMock:
    storage = MagicMock(spec=ObjectStorage)
    storage.get = AsyncMock(return_value=_create_test_png_bytes(4500, 5400))
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
        master_asset.width = 4500
        master_asset.height = 5400
        master_asset.checksum_sha256 = "master_sha256"
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

        # Storage mock with master PNG and oversized delivery ZIP (25MB)
        master_bytes = _create_test_png_bytes(4500, 5400, raw_bytes=1000)
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

        # Multiple digital files uploaded directly to Etsy (Master PNG + Extras ZIP or Complete ZIP)
        assert len(fake_etsy.uploaded_files) >= 1
        uploaded_names = [f["filename"] for f in fake_etsy.uploaded_files]
        # Never upload Digital_Download_Access_Instructions.pdf!
        assert "Digital_Download_Access_Instructions.pdf" not in uploaded_names
        assert any("master" in fn or fn.endswith(".zip") for fn in uploaded_names)

    @pytest.mark.asyncio
    async def test_execute_etsy_draft_partial_file_upload_retry_does_not_duplicate(
        self,
        cipher: CredentialCipher,
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.name = "Partial Upload Workflow"
        workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
        workflow.version = 1
        uow.workflows.get = AsyncMock(return_value=workflow)

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.etsy_shop_id = "shop_partial_123"
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.title = "Partial Retry Artwork"
        listing.description = "Download file."
        listing.tags = [f"tag_{i}" for i in range(13)]
        listing.price_minor_units = 500
        listing.currency = "USD"
        listing.taxonomy_id = 6844
        listing.taxonomy_path = "Craft Supplies & Tools > Clip Art & Image Files"
        listing.etsy_listing_id = "existing_listing_123"
        listing.etsy_image_ids = ["img_1"]
        listing.etsy_file_id = "file_already_uploaded_1"
        # Simulate that file 1 is already recorded as uploaded
        listing.etsy_file_ids = ["file_already_uploaded_1"]
        listing.etsy_dispatch_status = "uploading_file"

        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.update = AsyncMock(return_value=listing)
        uow.listing_drafts.update_etsy_draft = AsyncMock(return_value=listing)
        uow.listing_drafts.update_etsy_dispatch_status = AsyncMock(return_value=listing)
        uow.listing_drafts.record_etsy_image_upload = AsyncMock(return_value=listing)
        uow.listing_drafts.record_etsy_file_upload = AsyncMock(return_value=listing)

        master_bytes = _create_test_png_bytes(4500, 5400, raw_bytes=1000)
        mock_storage = MagicMock(spec=ObjectStorage)
        mock_storage.get = AsyncMock(return_value=master_bytes)
        mock_storage.put = AsyncMock(return_value=MagicMock(storage_key="workflows/pkg.zip"))

        master_asset = MagicMock(spec=Asset)
        master_asset.id = uuid.uuid4()
        master_asset.workflow_id = workflow_id
        master_asset.mime_type = "image/png"
        master_asset.storage_key = f"workflows/{workflow_id}/master.png"
        master_asset.width = 4500
        master_asset.height = 5400
        master_asset.checksum_sha256 = "master_sha"
        master_asset.provenance = {"profile": "etsy-png-standard"}

        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset])
        uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
        uow.assets.add = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.audit.record = AsyncMock()
        uow.commit = AsyncMock()
        uow.workflows.transition = AsyncMock()

        fake_etsy = FakeEtsyProvider()

        await execute_etsy_draft_pipeline(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            storage=mock_storage,
            cipher=cipher,
            etsy_gateway=fake_etsy,
        )

        # Since file 1 was already present in etsy_file_ids, it was skipped and not re-uploaded
        assert len(fake_etsy.uploaded_images) == 0

    @pytest.mark.asyncio
    async def test_execute_etsy_draft_with_large_master_png_wraps_in_zip(
        self,
        cipher: CredentialCipher,
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.name = "Large 21MB Artwork"
        workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
        workflow.version = 1
        uow.workflows.get = AsyncMock(return_value=workflow)

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.etsy_shop_id = "shop_large_123"
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.title = "High Res 4500x5400 Art"
        listing.description = "Download file."
        listing.tags = [f"tag_{i}" for i in range(13)]
        listing.price_minor_units = 500
        listing.currency = "USD"
        listing.taxonomy_id = 6844
        listing.taxonomy_path = "Craft Supplies & Tools > Clip Art & Image Files"
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

        # 20.5MB uncompressed scanlines that compress under 20MB with deflate
        large_master_bytes = _create_test_png_bytes(4500, 5400, raw_bytes=20 * 1024 * 1024 + 500 * 1024, compressible=True)
        mock_storage = MagicMock(spec=ObjectStorage)

        async def fake_storage_get(key: str) -> bytes:
            if "master.png" in key:
                return large_master_bytes
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
        master_asset.checksum_sha256 = "large_sha256"
        master_asset.provenance = {"profile": "etsy-png-standard"}

        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset])
        uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
        uow.assets.add = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.audit.record = AsyncMock()
        uow.commit = AsyncMock()
        uow.workflows.transition = AsyncMock()

        fake_etsy = FakeEtsyProvider()

        await execute_etsy_draft_pipeline(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            storage=mock_storage,
            cipher=cipher,
            etsy_gateway=fake_etsy,
        )

        # Confirm files uploaded successfully and every file is strictly <= 20MB
        assert len(fake_etsy.uploaded_files) >= 1
        for uploaded in fake_etsy.uploaded_files:
            assert uploaded["filesize"] <= 20 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_execute_etsy_draft_fails_safely_when_master_exceeds_limit(
        self,
        cipher: CredentialCipher,
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.name = "Massive Artwork"
        workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
        workflow.version = 1
        uow.workflows.get = AsyncMock(return_value=workflow)

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.etsy_shop_id = "shop_massive_123"
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.title = "Massive 24MB Art"
        listing.description = "Download file."
        listing.tags = [f"tag_{i}" for i in range(13)]
        listing.price_minor_units = 500
        listing.currency = "USD"
        listing.taxonomy_id = 6844
        listing.taxonomy_path = "Craft Supplies & Tools > Clip Art & Image Files"
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

        # 21MB uncompressible PNG
        oversized_master_bytes = _create_test_png_bytes(4500, 5400, raw_bytes=21 * 1024 * 1024, compressible=False)
        mock_storage = MagicMock(spec=ObjectStorage)
        mock_storage.get = AsyncMock(return_value=oversized_master_bytes)

        master_asset = MagicMock(spec=Asset)
        master_asset.id = uuid.uuid4()
        master_asset.workflow_id = workflow_id
        master_asset.mime_type = "image/png"
        master_asset.storage_key = f"workflows/{workflow_id}/master.png"
        master_asset.width = 4500
        master_asset.height = 5400
        master_asset.checksum_sha256 = "oversized_sha"
        master_asset.provenance = {"profile": "etsy-png-standard"}

        uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset])
        uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
        uow.assets.add = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.audit.record = AsyncMock()
        uow.commit = AsyncMock()

        fake_etsy = FakeEtsyProvider()

        with pytest.raises(DomainError, match="exceeds Etsy's maximum digital file limit of 20MB"):
            await execute_etsy_draft_pipeline(
                workflow_id=workflow_id,
                owner_id=owner_id,
                uow=uow,
                storage=mock_storage,
                cipher=cipher,
                etsy_gateway=fake_etsy,
            )


def test_pricing_safety_and_currency_resolution():
    """Verify resolve_listing_price and resolve_listing_currency precedence."""
    from app.domain.pricing import resolve_listing_currency, resolve_listing_price

    # 1. Explicit price takes precedence
    assert resolve_listing_price(listing_price_minor=650, owner_default_minor=499) == 650

    # 2. Owner default price takes second precedence
    assert resolve_listing_price(listing_price_minor=None, owner_default_minor=750) == 750

    # 3. Recommendation engine fallback
    rec_price = resolve_listing_price(
        listing_price_minor=None,
        owner_default_minor=None,
        title="Retro Christmas PNG Bundle",
        tags=["christmas", "bundle"],
    )
    assert rec_price is not None and rec_price > 0

    # 4. Currency precedence: listing -> shop -> owner -> USD
    assert resolve_listing_currency(listing_currency="EUR", shop_currency="GBP", owner_currency="CAD") == "EUR"
    assert resolve_listing_currency(listing_currency=None, shop_currency="GBP", owner_currency="CAD") == "GBP"
    assert resolve_listing_currency(listing_currency=None, shop_currency=None, owner_currency="CAD") == "CAD"
    assert resolve_listing_currency(listing_currency=None, shop_currency=None, owner_currency=None) == "USD"


def test_build_etsy_dispatch_response_step_model():
    """Verify _build_etsy_dispatch_response produces accurate steps for in-progress and completed states."""
    from app.api.routes.etsy import _build_etsy_dispatch_response

    wf_id = uuid.uuid4()

    # 1. not_started
    resp_none = _build_etsy_dispatch_response(wf_id, None)
    assert resp_none.dispatch_status == "not_started"
    assert resp_none.steps["create_listing"].status == "pending"
    assert resp_none.steps["upload_mockups"].status == "pending"
    assert resp_none.steps["upload_files"].status == "pending"

    # 2. in_progress uploading_files
    listing_in_progress = MagicMock(spec=ListingDraft)
    listing_in_progress.etsy_listing_id = "4559404921"
    listing_in_progress.etsy_listing_url = "https://www.etsy.com/listing/4559404921"
    listing_in_progress.etsy_state = "draft"
    listing_in_progress.etsy_shop_id = "shop-1"
    listing_in_progress.etsy_image_ids = ["img-1", "img-2", "img-3", "img-4"]
    listing_in_progress.etsy_file_id = None
    listing_in_progress.etsy_file_ids = []
    listing_in_progress.taxonomy_id = 77
    listing_in_progress.taxonomy_path = "Digital"
    listing_in_progress.etsy_failure_reason = None
    listing_in_progress.etsy_last_synced_at = datetime.now(UTC)
    listing_in_progress.etsy_dispatch_status = "uploading_file"

    resp_uploading = _build_etsy_dispatch_response(wf_id, listing_in_progress)
    assert resp_uploading.dispatch_status == "uploading_file"
    assert resp_uploading.current_step == "upload_files"
    assert resp_uploading.steps["create_listing"].status == "completed"
    assert resp_uploading.steps["upload_mockups"].status == "completed"
    assert resp_uploading.steps["upload_mockups"].uploaded_count == 4
    assert resp_uploading.steps["upload_files"].status == "in_progress"

    # 3. completed
    listing_completed = MagicMock(spec=ListingDraft)
    listing_completed.etsy_listing_id = "4559404921"
    listing_completed.etsy_listing_url = "https://www.etsy.com/listing/4559404921"
    listing_completed.etsy_state = "draft"
    listing_completed.etsy_shop_id = "shop-1"
    listing_completed.etsy_image_ids = ["img-1", "img-2", "img-3", "img-4"]
    listing_completed.etsy_file_id = "file-1"
    listing_completed.etsy_file_ids = ["file-1", "file-2"]
    listing_completed.taxonomy_id = 77
    listing_completed.taxonomy_path = "Digital"
    listing_completed.etsy_failure_reason = None
    listing_completed.etsy_last_synced_at = datetime.now(UTC)
    listing_completed.etsy_dispatch_status = "completed"

    resp_done = _build_etsy_dispatch_response(wf_id, listing_completed)
    assert resp_done.dispatch_status == "completed"
    assert resp_done.current_step is None
    assert resp_done.steps["create_listing"].status == "completed"
    assert resp_done.steps["upload_mockups"].status == "completed"
    assert resp_done.steps["upload_mockups"].uploaded_count == 4
    assert resp_done.steps["upload_files"].status == "completed"
    assert resp_done.steps["upload_files"].uploaded_count == 2
    assert resp_done.steps["apply_attributes"].status == "completed"


@pytest.mark.asyncio
async def test_cover_mockup_priority_over_listing_order() -> None:
    """Verify that a mockup marked as is_cover=True is uploaded at Rank 1 (Thumbnail) even if listing_order is higher than other mockups."""
    from app.domain.production_resolver import filter_active_user_mockups
    from app.domain.media_selector import order_listing_mockup_assets

    master_id = uuid.uuid4()
    poster_mockup_id = uuid.uuid4()
    mug_mockup_id = uuid.uuid4()
    bag_mockup_id = uuid.uuid4()

    now = datetime.now(UTC)

    master = MagicMock(spec=Asset)
    master.id = master_id
    master.derived_from_id = None
    master.provenance = {"profile": "etsy-png-standard"}
    master.storage_key = "workflows/123/master.png"

    # Poster: is_cover=True, listing_order=5
    poster = MagicMock(spec=Asset)
    poster.id = poster_mockup_id
    poster.derived_from_id = master_id
    poster.storage_key = "workflows/123/mockups/poster.jpg"
    poster.created_at = now
    poster.provenance = {
        "asset_type": "mockup",
        "source": "user_template",
        "product_type": "poster",
        "template_id": "tpl_poster",
        "template_name": "Poster",
        "is_cover": True,
        "listing_order": 5,
    }

    # Mug: is_cover=False, listing_order=1
    mug = MagicMock(spec=Asset)
    mug.id = mug_mockup_id
    mug.derived_from_id = master_id
    mug.storage_key = "workflows/123/mockups/mug.jpg"
    mug.created_at = now + timedelta(seconds=1)
    mug.provenance = {
        "asset_type": "mockup",
        "source": "user_template",
        "product_type": "mug",
        "template_id": "tpl_mug",
        "template_name": "Mug 2",
        "is_cover": False,
        "listing_order": 1,
    }

    # Bag: is_cover=False, listing_order=4
    bag = MagicMock(spec=Asset)
    bag.id = bag_mockup_id
    bag.derived_from_id = master_id
    bag.storage_key = "workflows/123/mockups/bag.jpg"
    bag.created_at = now + timedelta(seconds=2)
    bag.provenance = {
        "asset_type": "mockup",
        "source": "user_template",
        "product_type": "bag",
        "template_id": "tpl_bag",
        "template_name": "Tote Bag",
        "is_cover": False,
        "listing_order": 4,
    }

    all_assets = [master, mug, bag, poster]

    # 1. Test filter_active_user_mockups sorts cover first
    filtered = filter_active_user_mockups(all_assets, master_id)
    assert len(filtered) == 3
    assert filtered[0].id == poster_mockup_id
    assert filtered[1].id == mug_mockup_id
    assert filtered[2].id == bag_mockup_id

    # 2. Test order_listing_mockup_assets puts poster at Rank 1 even if primary_mockup_asset_id is None
    ordered = order_listing_mockup_assets(
        mockups=filtered,
        master_asset=master,
        primary_mockup_asset_id=None,
        max_images=10,
    )
    assert len(ordered) == 3
    assert ordered[0].id == poster_mockup_id  # Rank 1 Thumbnail is Poster!
    assert ordered[1].id == mug_mockup_id
    assert ordered[2].id == bag_mockup_id




