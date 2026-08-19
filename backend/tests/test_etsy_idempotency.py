"""Tests for Etsy draft pipeline idempotency and partial-failure recovery."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.etsy_draft import execute_etsy_draft_pipeline
from app.domain.workflow import RunStatus
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
    ShopConnection,
)
from app.infrastructure.security import CredentialCipher
from app.ports.providers import ObjectStorage
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


@pytest.mark.asyncio
async def test_idempotent_retry_reuses_existing_listing_id(
    cipher: CredentialCipher,
    mock_storage: MagicMock,
) -> None:
    """When a worker retries after an existing draft was created, it reuses the Etsy listing ID without creating duplicates."""
    workflow_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    uow = MagicMock()
    uow.commit = AsyncMock()
    uow.audit = MagicMock()
    uow.audit.record = AsyncMock()

    workflow = MagicMock(spec=ProductWorkflow)
    workflow.id = workflow_id
    workflow.owner_id = owner_id
    workflow.name = "Vintage Astronomy PNG"
    workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
    workflow.version = 2
    uow.workflows.get = AsyncMock(return_value=workflow)
    uow.workflows.transition = AsyncMock()

    conn = MagicMock(spec=ShopConnection)
    conn.id = uuid.uuid4()
    conn.user_id = owner_id
    conn.etsy_shop_id = "shop_999"
    conn.etsy_shop_name = "AstroStudio"
    conn.connection_status = "connected"
    conn.is_connected = True
    conn.key_version = cipher.key_version
    conn.ciphertext_access_token = cipher.encrypt("token")
    conn.ciphertext_refresh_token = cipher.encrypt("refresh")
    conn.token_expires_at = datetime.now(UTC) + timedelta(hours=2)
    uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
    uow.telegram_connections.get_by_user_id = AsyncMock(return_value=None)

    valid_tags = [f"tag_{i}" for i in range(13)]

    # Pre-existing listing on Etsy from a prior partial run
    existing_listing_id = "1122334455"
    listing = MagicMock(spec=ListingDraft)
    listing.id = uuid.uuid4()
    listing.workflow_id = workflow_id
    listing.title = "Vintage Astronomy PNG Design"
    listing.description = "Download file."
    listing.tags = valid_tags
    listing.price_minor_units = 499
    listing.currency = "USD"
    listing.taxonomy_id = 1049
    listing.etsy_listing_id = existing_listing_id  # Already set!
    listing.etsy_image_ids = ["img_1"]  # Image 1 already uploaded!
    listing.etsy_file_id = None  # File not yet uploaded
    listing.etsy_dispatch_status = "uploading_images"

    uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
    uow.listing_drafts.update = AsyncMock(return_value=listing)
    uow.listing_drafts.update_etsy_draft = AsyncMock(return_value=listing)
    uow.listing_drafts.update_etsy_dispatch_status = AsyncMock(return_value=listing)
    uow.listing_drafts.record_etsy_image_upload = AsyncMock(return_value=listing)
    uow.listing_drafts.record_etsy_file_upload = AsyncMock(return_value=listing)

    now = datetime.now(UTC)
    master_asset = MagicMock(spec=Asset)
    master_asset.id = uuid.uuid4()
    master_asset.workflow_id = workflow_id
    master_asset.mime_type = "image/png"
    master_asset.storage_key = f"workflows/{workflow_id}/master.png"
    master_asset.created_at = now
    master_asset.provenance = {"profile": "etsy-png-standard"}

    mockup_1 = MagicMock(spec=Asset)
    mockup_1.id = uuid.uuid4()
    mockup_1.workflow_id = workflow_id
    mockup_1.mime_type = "image/jpeg"
    mockup_1.derived_from_id = master_asset.id
    mockup_1.storage_key = f"workflows/{workflow_id}/mockups/tshirt.jpg"
    mockup_1.created_at = now + timedelta(seconds=1)
    mockup_1.provenance = {
        "asset_type": "mockup",
        "source": "user_template",
        "template_id": "tpl_1",
        "is_cover": True,
        "listing_order": 1,
    }

    mockup_2 = MagicMock(spec=Asset)
    mockup_2.id = uuid.uuid4()
    mockup_2.workflow_id = workflow_id
    mockup_2.mime_type = "image/jpeg"
    mockup_2.derived_from_id = master_asset.id
    mockup_2.storage_key = f"workflows/{workflow_id}/mockups/tote.jpg"
    mockup_2.created_at = now + timedelta(seconds=2)
    mockup_2.provenance = {
        "asset_type": "mockup",
        "source": "user_template",
        "template_id": "tpl_2",
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

    uow.assets.list_for_workflow = AsyncMock(return_value=[master_asset, mockup_1, mockup_2, zip_asset])
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
        telegram_gateway=None,
    )

    # ZERO new listings created (reused existing_listing_id)
    assert len(fake_etsy.created_listings) == 0

    # Mockup 1 was already uploaded, only Mockup 2 (rank 2) is uploaded!
    assert len(fake_etsy.uploaded_images) == 1
    assert fake_etsy.uploaded_images[0]["rank"] == 2
    assert fake_etsy.uploaded_images[0]["listing_id"] == existing_listing_id

    # ZIP file is uploaded
    assert len(fake_etsy.uploaded_files) == 1
    assert fake_etsy.uploaded_files[0]["listing_id"] == existing_listing_id
