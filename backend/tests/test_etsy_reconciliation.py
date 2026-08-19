"""Tests for automatic reconciliation of Etsy drafts that are deleted externally."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.etsy_draft import (
    execute_etsy_draft_pipeline,
    reconcile_etsy_draft,
)
from app.domain.enums import AuditAction
from app.domain.errors import EntityNotFoundError
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


class TestEtsyReconciliation:
    @pytest.mark.asyncio
    async def test_reconcile_existing_listing_stays_intact(self, cipher: CredentialCipher) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        listing_id = "etsy_listing_999"

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.ETSY_DRAFT_CREATED
        workflow.version = 5

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.etsy_listing_id = listing_id
        listing.etsy_shop_id = "shop_123"
        listing.etsy_state = "draft"
        listing.etsy_dispatch_status = "completed"
        listing.title = "Cute Cat PNG"

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.connection_status = "connected"
        conn.etsy_shop_id = "shop_123"
        conn.is_token_expired = False
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("valid_token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.commit = AsyncMock()

        fake_etsy = FakeEtsyProvider(default_shop_id="shop_123")
        fake_etsy.created_listings.append(
            {"listing_id": listing_id, "title": "Cute Cat PNG"}
        )

        res = await reconcile_etsy_draft(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            etsy_gateway=fake_etsy,
            cipher=cipher,
        )

        assert res.reconciled is True
        assert res.exists_on_etsy is True
        assert res.status == "synced"
        assert res.etsy_listing_id == listing_id
        # State machine was not touched
        assert uow.workflows.transition.call_count == 0

    @pytest.mark.asyncio
    async def test_reconcile_deleted_listing_clears_local_state_and_transitions_workflow(
        self, cipher: CredentialCipher
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        listing_id = "etsy_listing_deleted_123"

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.ETSY_DRAFT_CREATED
        workflow.version = 3

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.etsy_listing_id = listing_id
        listing.etsy_shop_id = "shop_123"
        listing.etsy_state = "draft"
        listing.etsy_image_ids = ["img_1", "img_2"]
        listing.etsy_file_id = "file_1"
        listing.etsy_file_ids = ["file_1"]
        listing.etsy_dispatch_status = "completed"
        # Assets & metadata that must remain intact
        listing.title = "Cute Cat Clipart"
        listing.description = "High quality 300 DPI PNG"
        listing.tags = ["cat", "clipart"]
        listing.taxonomy_id = 6844
        listing.taxonomy_path = "Craft Supplies & Tools > Clip Art & Image Files"

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.connection_status = "connected"
        conn.etsy_shop_id = "shop_123"
        conn.is_token_expired = False
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("valid_token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.clear_etsy_draft_state = AsyncMock(return_value=listing)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.workflows.transition = AsyncMock()
        uow.audit.record = AsyncMock()
        uow.commit = AsyncMock()

        fake_etsy = FakeEtsyProvider(default_shop_id="shop_123")
        fake_etsy.mark_listing_deleted(listing_id)

        res = await reconcile_etsy_draft(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            etsy_gateway=fake_etsy,
            cipher=cipher,
        )

        assert res.reconciled is True
        assert res.exists_on_etsy is False
        assert res.status == "draft_removed"
        assert res.etsy_listing_id is None

        # Verify clear_etsy_draft_state was called
        uow.listing_drafts.clear_etsy_draft_state.assert_awaited_once_with(
            listing.id, last_synced_at=pytest.approx(datetime.now(UTC), abs=timedelta(seconds=5))
        )

        # Verify workflow transitioned back to READY_FOR_ETSY_DRAFT
        uow.workflows.transition.assert_awaited_once_with(
            workflow,
            to_state=RunStatus.READY_FOR_ETSY_DRAFT,
            expected_version=3,
            reason="Etsy draft was deleted on Etsy. Reconciled local state back to ready for draft.",
            actor=str(owner_id),
        )

        # Verify audit event recorded
        uow.audit.record.assert_awaited_once()
        audit_call = uow.audit.record.call_args[1]
        assert audit_call["action"] == AuditAction.ETSY_DRAFT_REMOVED_EXTERNALLY
        assert audit_call["entity_id"] == listing.id
        assert audit_call["actor"] == str(owner_id)
        assert audit_call["metadata"]["previous_etsy_listing_id"] == listing_id
        assert audit_call["metadata"]["reason"] == "listing_not_found_on_etsy"

    @pytest.mark.asyncio
    async def test_transient_error_does_not_clear_draft(self, cipher: CredentialCipher) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        listing_id = "etsy_listing_transient"

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.ETSY_DRAFT_CREATED

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.etsy_listing_id = listing_id

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.connection_status = "connected"
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("valid_token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

        fake_etsy = FakeEtsyProvider()

        # Test timeout / 5xx / 429
        for flag_name in ("get_listing_timeout", "get_listing_server_error", "get_listing_rate_limited"):
            setattr(fake_etsy, flag_name, True)

            res = await reconcile_etsy_draft(
                workflow_id=workflow_id,
                owner_id=owner_id,
                uow=uow,
                etsy_gateway=fake_etsy,
                cipher=cipher,
            )

            assert res.reconciled is False
            assert res.exists_on_etsy is True
            assert res.status == "transient_error"
            assert res.etsy_listing_id == listing_id
            assert uow.listing_drafts.clear_etsy_draft_state.call_count == 0
            assert uow.workflows.transition.call_count == 0

            setattr(fake_etsy, flag_name, False)

    @pytest.mark.asyncio
    async def test_auth_revoked_does_not_clear_draft(self, cipher: CredentialCipher) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        listing_id = "etsy_listing_auth_test"

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.ETSY_DRAFT_CREATED

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.etsy_listing_id = listing_id

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.connection_status = "connected"
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("valid_token")
        conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

        fake_etsy = FakeEtsyProvider()
        fake_etsy.revoked_token = True

        res = await reconcile_etsy_draft(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            etsy_gateway=fake_etsy,
            cipher=cipher,
        )

        assert res.reconciled is False
        assert res.status == "reauth_required"
        assert res.etsy_listing_id == listing_id
        assert uow.listing_drafts.clear_etsy_draft_state.call_count == 0
        assert uow.workflows.transition.call_count == 0

    @pytest.mark.asyncio
    async def test_cross_owner_reconciliation_rejected(self, cipher: CredentialCipher) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        real_owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = real_owner_id

        uow.workflows.get = AsyncMock(return_value=workflow)
        fake_etsy = FakeEtsyProvider()

        with pytest.raises(EntityNotFoundError):
            await reconcile_etsy_draft(
                workflow_id=workflow_id,
                owner_id=other_user_id,
                uow=uow,
                etsy_gateway=fake_etsy,
                cipher=cipher,
            )

    @pytest.mark.asyncio
    async def test_recreate_draft_after_deletion_flow(
        self,
        cipher: CredentialCipher,
        mock_storage: MagicMock,
    ) -> None:
        uow = MagicMock()
        workflow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        now = datetime.now(UTC)

        workflow = MagicMock(spec=ProductWorkflow)
        workflow.id = workflow_id
        workflow.owner_id = owner_id
        workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
        workflow.version = 1

        listing = MagicMock(spec=ListingDraft)
        listing.id = uuid.uuid4()
        listing.workflow_id = workflow_id
        listing.title = "Cute Watercolor Kitten PNG"
        listing.description = "Transparent PNG 300 DPI"
        listing.tags = [
            "cat",
            "kitten",
            "png",
            "clipart",
            "cat art",
            "watercolor",
            "digital download",
            "printable",
            "cat lover",
            "feline",
            "cute cat",
            "cat graphics",
            "pet portrait",
        ]
        listing.price_minor_units = 450
        listing.currency = "USD"
        listing.taxonomy_id = 6844
        listing.taxonomy_path = "Craft Supplies & Tools > Clip Art & Image Files"
        listing.etsy_listing_id = None
        listing.etsy_dispatch_status = "not_started"
        listing.etsy_image_ids = []
        listing.etsy_file_id = None
        listing.etsy_file_ids = []
        listing.version = 1

        conn = MagicMock(spec=ShopConnection)
        conn.is_connected = True
        conn.connection_status = "connected"
        conn.etsy_shop_id = "shop_123"
        conn.etsy_shop_name = "KittenStudio"
        conn.key_version = 1
        conn.ciphertext_access_token = cipher.encrypt("token_123")
        conn.token_expires_at = now + timedelta(hours=2)
        conn.is_token_expired = False

        master_asset = MagicMock(spec=Asset)
        master_asset.id = uuid.uuid4()
        master_asset.workflow_id = workflow_id
        master_asset.mime_type = "image/png"
        master_asset.storage_key = f"workflows/{workflow_id}/master.png"
        master_asset.created_at = now
        master_asset.provenance = {"is_master": True, "asset_type": "transparent_png"}

        mockup_asset = MagicMock(spec=Asset)
        mockup_asset.id = uuid.uuid4()
        mockup_asset.workflow_id = workflow_id
        mockup_asset.mime_type = "image/jpeg"
        mockup_asset.derived_from_id = master_asset.id
        mockup_asset.storage_key = f"workflows/{workflow_id}/mockups/tote.jpg"
        mockup_asset.created_at = now + timedelta(seconds=1)
        mockup_asset.provenance = {
            "asset_type": "mockup",
            "source": "user_template",
            "template_id": "tpl_1",
            "is_cover": True,
            "listing_order": 1,
        }

        zip_asset = MagicMock(spec=Asset)
        zip_asset.id = uuid.uuid4()
        zip_asset.workflow_id = workflow_id
        zip_asset.mime_type = "application/zip"
        zip_asset.storage_key = f"workflows/{workflow_id}/packages/package.zip"
        zip_asset.created_at = now + timedelta(seconds=2)
        zip_asset.provenance = {"kind": "customer_package"}

        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
        uow.listing_drafts.update = AsyncMock(return_value=listing)
        uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
        uow.assets.list_for_workflow = AsyncMock(
            return_value=[master_asset, mockup_asset, zip_asset]
        )
        uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
        uow.assets.add = AsyncMock()
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.audit.record = AsyncMock()
        uow.commit = AsyncMock()

        async def fake_update_etsy_draft(draft_id: uuid.UUID, **kwargs: object) -> ListingDraft:
            listing.etsy_listing_id = str(kwargs.get("etsy_listing_id"))
            listing.etsy_shop_id = str(kwargs.get("etsy_shop_id"))
            listing.etsy_listing_url = str(kwargs.get("etsy_listing_url"))
            listing.etsy_state = str(kwargs.get("etsy_state"))
            listing.etsy_dispatch_status = str(kwargs.get("etsy_dispatch_status"))
            return listing

        async def fake_clear_etsy_draft(draft_id: uuid.UUID, **kwargs: object) -> ListingDraft:
            listing.etsy_listing_id = None
            listing.etsy_shop_id = None
            listing.etsy_listing_url = None
            listing.etsy_state = None
            listing.etsy_image_ids = []
            listing.etsy_file_id = None
            listing.etsy_file_ids = []
            listing.etsy_dispatch_status = "not_started"
            return listing

        async def fake_record_image(draft_id: uuid.UUID, **kwargs: object) -> ListingDraft:
            listing.etsy_image_ids = [*list(listing.etsy_image_ids or []), str(kwargs.get("image_id"))]
            return listing

        async def fake_record_file(draft_id: uuid.UUID, **kwargs: object) -> ListingDraft:
            listing.etsy_file_id = str(kwargs.get("file_id"))
            listing.etsy_file_ids = [*list(listing.etsy_file_ids or []), str(kwargs.get("file_id"))]
            return listing

        async def fake_update_dispatch_status(
            draft_id: uuid.UUID, **kwargs: object
        ) -> ListingDraft:
            listing.etsy_dispatch_status = str(kwargs.get("status"))
            return listing

        async def fake_transition(wf: ProductWorkflow, **kwargs: object) -> None:
            wf.state = kwargs["to_state"]  # type: ignore[assignment]
            wf.version += 1

        uow.listing_drafts.update_etsy_draft = AsyncMock(side_effect=fake_update_etsy_draft)
        uow.listing_drafts.clear_etsy_draft_state = AsyncMock(side_effect=fake_clear_etsy_draft)
        uow.listing_drafts.record_etsy_image_upload = AsyncMock(side_effect=fake_record_image)
        uow.listing_drafts.record_etsy_file_upload = AsyncMock(side_effect=fake_record_file)
        uow.listing_drafts.update_etsy_dispatch_status = AsyncMock(
            side_effect=fake_update_dispatch_status
        )
        uow.workflows.transition = AsyncMock(side_effect=fake_transition)

        fake_etsy = FakeEtsyProvider(default_shop_id="shop_123")
        fake_tg = MagicMock()
        fake_tg.send_message = AsyncMock()

        # Step 1: Initial Dispatch
        await execute_etsy_draft_pipeline(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            storage=mock_storage,
            cipher=cipher,
            etsy_gateway=fake_etsy,
            telegram_gateway=fake_tg,
        )

        first_listing_id = listing.etsy_listing_id
        assert first_listing_id is not None
        assert workflow.state == RunStatus.ETSY_DRAFT_CREATED
        assert listing.etsy_dispatch_status == "completed"

        # Step 2: Listing deleted on Etsy
        fake_etsy.mark_listing_deleted(first_listing_id)

        # Step 3: Reconcile detected deletion
        reconcile_res = await reconcile_etsy_draft(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            etsy_gateway=fake_etsy,
            cipher=cipher,
        )

        assert reconcile_res.reconciled is True
        assert reconcile_res.exists_on_etsy is False
        assert reconcile_res.status == "draft_removed"
        assert listing.etsy_listing_id is None
        assert workflow.state == RunStatus.READY_FOR_ETSY_DRAFT
        assert listing.etsy_dispatch_status == "not_started"
        # Local artwork & metadata still fully preserved
        assert listing.title == "Cute Watercolor Kitten PNG"
        assert listing.taxonomy_id == 6844

        # Step 4: Re-dispatch a fresh Etsy draft
        await execute_etsy_draft_pipeline(
            workflow_id=workflow_id,
            owner_id=owner_id,
            uow=uow,
            storage=mock_storage,
            cipher=cipher,
            etsy_gateway=fake_etsy,
            telegram_gateway=fake_tg,
        )

        second_listing_id = listing.etsy_listing_id
        assert second_listing_id is not None
        assert second_listing_id != first_listing_id
        assert workflow.state == RunStatus.ETSY_DRAFT_CREATED
        assert listing.etsy_dispatch_status == "completed"

