"""Unit tests for Etsy API routes (auth, connection status, disconnect, draft trigger)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_credential_cipher,
    get_current_user,
    get_etsy_gateway,
    get_redis,
    get_storage,
    get_uow,
)
from app.domain.workflow import RunStatus
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
    ShopConnection,
    User,
)
from app.infrastructure.security import CredentialCipher
from app.main import create_app
from app.providers.fake import FakeEtsyProvider
from app.settings import Settings


@pytest.fixture
def test_user() -> User:
    return User(id=uuid.uuid4(), email="artist@studio.com", password_hash="hash")


@pytest.fixture
def cipher() -> CredentialCipher:
    return CredentialCipher("test-encryption-key-32-chars-long!", key_version=1)


@pytest.fixture
def fake_redis() -> AsyncMock:
    storage: dict[str, str] = {}
    redis = AsyncMock()

    async def _set(key: str, val: str, ex: int | None = None) -> bool:
        storage[key] = val
        return True

    async def _get(key: str) -> str | None:
        return storage.get(key)

    async def _delete(key: str) -> int:
        if key in storage:
            del storage[key]
            return 1
        return 0

    redis.set.side_effect = _set
    redis.get.side_effect = _get
    redis.delete.side_effect = _delete
    return redis


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.commit = AsyncMock()
    uow.outbox = MagicMock()
    uow.outbox.add = AsyncMock()
    return uow


def _make_test_png() -> bytes:
    import struct
    import zlib
    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 4500, 5400, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw_scanlines = b"\x00" + b"\xff\x00\x00\xff" * 100
    compressed_idat = zlib.compress(raw_scanlines, level=0)
    idat_crc = zlib.crc32(b"IDAT" + compressed_idat)
    idat = struct.pack(">I", len(compressed_idat)) + b"IDAT" + compressed_idat + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND")
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return header + ihdr + idat + iend


@pytest.fixture
def mock_storage() -> MagicMock:
    storage = MagicMock()
    valid_png = _make_test_png()
    storage.get = AsyncMock(return_value=valid_png)
    storage.put = AsyncMock(return_value=MagicMock(storage_key="workflows/pkg.zip"))
    return storage


@pytest.fixture
def client(
    settings: Settings,
    test_user: User,
    mock_uow: MagicMock,
    fake_redis: AsyncMock,
    cipher: CredentialCipher,
    mock_storage: MagicMock,
) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_uow] = lambda: mock_uow
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_credential_cipher] = lambda: cipher
    app.dependency_overrides[get_etsy_gateway] = lambda: FakeEtsyProvider()
    app.dependency_overrides[get_storage] = lambda: mock_storage
    return TestClient(app)


def test_get_auth_connect_url(client: TestClient) -> None:
    response = client.get("/api/v1/auth/etsy/connect")
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "response_type=code" in data["authorization_url"]


def test_oauth_callback_success_redirects_to_settings(
    client: TestClient,
    fake_redis: AsyncMock,
    test_user: User,
    mock_uow: MagicMock,
    cipher: CredentialCipher,
) -> None:
    state = "state_xyz"
    verifier = "verifier_123"

    fake_conn = MagicMock(spec=ShopConnection)
    fake_conn.id = uuid.uuid4()
    fake_conn.user_id = test_user.id
    fake_conn.etsy_shop_id = "shop_1"
    fake_conn.etsy_shop_name = "Studio"
    fake_conn.connection_status = "connected"
    fake_conn.is_connected = True
    fake_conn.ciphertext_access_token = cipher.encrypt("token")
    fake_conn.key_version = cipher.key_version
    mock_uow.shop_connections.upsert = AsyncMock(return_value=fake_conn)
    mock_uow.audit.record = AsyncMock()

    # Pre-seed state in redis
    fake_redis.get.side_effect = None
    fake_redis.get = AsyncMock(
        return_value=json.dumps({"owner_id": str(test_user.id), "code_verifier": verifier})
    )

    response = client.get(
        f"/api/v1/auth/etsy/callback?code=test_code&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "etsy=connected" in response.headers["location"]


def test_get_integrations_etsy_disconnected(
    client: TestClient,
    mock_uow: MagicMock,
) -> None:
    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=None)
    response = client.get("/api/v1/integrations/etsy")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["connection_status"] == "disconnected"


def test_get_integrations_etsy_connected(
    client: TestClient,
    mock_uow: MagicMock,
    test_user: User,
) -> None:
    conn = MagicMock(spec=ShopConnection)
    conn.id = uuid.uuid4()
    conn.user_id = test_user.id
    conn.etsy_shop_id = "shop_100"
    conn.etsy_shop_name = "MyEtsyShop"
    conn.connection_status = "connected"
    conn.is_connected = True
    conn.granted_scopes = ["listings_w", "shops_r"]
    conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    conn.is_token_expired = False
    conn.last_refreshed_at = datetime.now(UTC)

    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

    response = client.get("/api/v1/integrations/etsy")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["shop_name"] == "MyEtsyShop"
    assert data["shop_id"] == "shop_100"
    assert data["token_health"] == "valid"
    assert "listings_w" in data["granted_scopes"]


def test_disconnect_etsy_integration(
    client: TestClient,
    mock_uow: MagicMock,
    test_user: User,
) -> None:
    conn = MagicMock(spec=ShopConnection)
    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)
    mock_uow.shop_connections.delete = AsyncMock()
    mock_uow.audit.record = AsyncMock()

    response = client.delete("/api/v1/integrations/etsy")
    assert response.status_code == 204
    mock_uow.shop_connections.delete.assert_called_once_with(conn)


def test_trigger_etsy_draft_endpoint(
    client: TestClient,
    mock_uow: MagicMock,
    test_user: User,
) -> None:
    workflow_id = uuid.uuid4()

    workflow = MagicMock(spec=ProductWorkflow)
    workflow.id = workflow_id
    workflow.owner_id = test_user.id
    workflow.name = "Celestial Art"
    workflow.state = RunStatus.READY_FOR_ETSY_DRAFT
    mock_uow.workflows.get = AsyncMock(return_value=workflow)

    conn = MagicMock(spec=ShopConnection)
    conn.id = uuid.uuid4()
    conn.user_id = test_user.id
    conn.connection_status = "connected"
    conn.is_connected = True
    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

    listing = MagicMock(spec=ListingDraft)
    listing.id = uuid.uuid4()
    listing.workflow_id = workflow_id
    listing.title = "Celestial Art Sublimation PNG"
    listing.description = "Download file."
    listing.tags = [f"tag {i}" for i in range(13)]
    listing.taxonomy_id = 6844
    listing.price_minor_units = 499
    listing.currency = "USD"
    listing.quantity = 999
    listing.sku = "NCP-CELESTIAL-001"
    listing.shop_section_id = None
    listing.should_auto_renew = False
    listing.etsy_properties = {}
    listing.primary_mockup_asset_id = None
    listing.etsy_listing_id = None
    listing.etsy_image_ids = []
    listing.etsy_file_id = None
    listing.etsy_dispatch_status = "not_started"
    listing.etsy_state = "draft"
    listing.etsy_shop_id = "shop_1"
    listing.etsy_listing_url = None
    listing.etsy_last_synced_at = None
    listing.etsy_failure_reason = None
    mock_uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
    mock_uow.listing_drafts.update_etsy_dispatch_status = AsyncMock(return_value=listing)

    master = MagicMock(spec=Asset)
    master.id = uuid.uuid4()
    master.workflow_id = workflow_id
    master.mime_type = "image/png"
    master.storage_key = f"workflows/{workflow_id}/master.png"
    master.created_at = datetime.now(UTC)
    master.provenance = {"profile": "etsy-png-standard"}

    zip_asset = MagicMock(spec=Asset)
    zip_asset.id = uuid.uuid4()
    zip_asset.workflow_id = workflow_id
    zip_asset.mime_type = "application/zip"
    zip_asset.storage_key = f"workflows/{workflow_id}/package.zip"
    zip_asset.created_at = datetime.now(UTC)
    zip_asset.provenance = {"kind": "customer_package"}

    mock_uow.assets.list_for_workflow = AsyncMock(return_value=[master, zip_asset])
    mock_uow.assets.get_by_checksum_sha256 = AsyncMock(return_value=None)
    mock_uow.assets.add = AsyncMock()
    mock_uow.listing_drafts.update = AsyncMock(return_value=listing)
    mock_uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])

    response = client.post(f"/api/v1/workflows/{workflow_id}/etsy/draft")
    assert response.status_code == 200
    data = response.json()
    assert data["dispatch_status"] == "queued"
    # Verify outbox message was created for worker
    mock_uow.outbox.add.assert_called_once_with(
        "create_etsy_draft_task", {"workflow_id": str(workflow_id)}
    )


def test_reconcile_etsy_draft_endpoint_when_draft_deleted(
    client: TestClient,
    mock_uow: MagicMock,
    test_user: User,
    cipher: CredentialCipher,
) -> None:
    workflow_id = uuid.uuid4()
    listing_id = "listing_to_reconcile_123"

    workflow = MagicMock(spec=ProductWorkflow)
    workflow.id = workflow_id
    workflow.owner_id = test_user.id
    workflow.state = RunStatus.ETSY_DRAFT_CREATED
    workflow.version = 2
    mock_uow.workflows.get = AsyncMock(return_value=workflow)

    conn = MagicMock(spec=ShopConnection)
    conn.id = uuid.uuid4()
    conn.user_id = test_user.id
    conn.connection_status = "connected"
    conn.is_connected = True
    conn.etsy_shop_id = "shop_1"
    conn.is_token_expired = False
    conn.key_version = 1
    conn.ciphertext_access_token = cipher.encrypt("token")
    conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=conn)

    listing = MagicMock(spec=ListingDraft)
    listing.id = uuid.uuid4()
    listing.workflow_id = workflow_id
    listing.title = "Cute Cat Clipart"
    listing.etsy_listing_id = listing_id
    listing.etsy_dispatch_status = "completed"
    listing.etsy_state = "draft"
    listing.etsy_shop_id = "shop_1"
    listing.etsy_image_ids = ["img_1"]
    listing.etsy_file_id = "file_1"
    listing.etsy_file_ids = ["file_1"]
    listing.etsy_listing_url = "https://etsy.com/edit/123"
    listing.etsy_last_synced_at = datetime.now(UTC)
    listing.etsy_failure_reason = None
    listing.taxonomy_id = 6844
    listing.taxonomy_path = "Craft Supplies & Tools > Clip Art & Image Files"
    mock_uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)

    async def fake_clear(draft_id: uuid.UUID, **kwargs: object) -> ListingDraft:
        listing.etsy_listing_id = None
        listing.etsy_dispatch_status = "not_started"
        listing.etsy_state = None
        listing.etsy_image_ids = []
        listing.etsy_file_id = None
        listing.etsy_file_ids = []
        listing.etsy_listing_url = None
        return listing

    mock_uow.listing_drafts.clear_etsy_draft_state = AsyncMock(side_effect=fake_clear)
    mock_uow.workflows.transition = AsyncMock()
    mock_uow.audit.record = AsyncMock()
    mock_uow.commit = AsyncMock()

    # Create a FakeEtsyProvider where listing_id is marked deleted
    fake_etsy = FakeEtsyProvider(default_shop_id="shop_1")
    fake_etsy.mark_listing_deleted(listing_id)
    app = client.app
    app.dependency_overrides[get_etsy_gateway] = lambda: fake_etsy

    response = client.post(f"/api/v1/workflows/{workflow_id}/etsy/reconcile")
    assert response.status_code == 200
    data = response.json()
    assert data["dispatch_status"] == "draft_removed"
    assert data["etsy_listing_id"] is None
    assert mock_uow.listing_drafts.clear_etsy_draft_state.call_count == 1
    assert mock_uow.workflows.transition.call_count == 1

