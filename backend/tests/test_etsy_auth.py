"""Tests for Etsy OAuth 2.0 PKCE and token management application service."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis

from app.application.etsy_auth import (
    ReauthorizationRequiredError,
    create_oauth_connect_url,
    disconnect_etsy,
    generate_pkce_pair,
    get_valid_access_token,
    handle_oauth_callback,
)
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.infrastructure.models import ShopConnection, User
from app.infrastructure.security import CredentialCipher
from app.ports.errors import ProviderError, ProviderErrorKind
from app.providers.fake import FakeEtsyProvider
from app.settings import Settings


@pytest.fixture
def cipher() -> CredentialCipher:
    return CredentialCipher("test-encryption-key-32-chars-long!", key_version=1)


@pytest.fixture
def fake_redis() -> AsyncMock:
    storage: dict[str, str] = {}
    redis = AsyncMock(spec=aioredis.Redis)

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
    uow = MagicMock(spec=UnitOfWork)
    uow.shop_connections = MagicMock()
    uow.audit = MagicMock()
    uow.audit.record = AsyncMock()
    uow.commit = AsyncMock()
    uow.session = MagicMock()
    return uow


def test_pkce_pair_generation() -> None:
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) > 0
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    assert challenge == expected


@pytest.mark.asyncio
async def test_create_oauth_connect_url(fake_redis: AsyncMock, settings: Settings) -> None:
    owner_id = uuid.uuid4()
    url = await create_oauth_connect_url(fake_redis, owner_id, settings)

    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert f"client_id={settings.resolved_etsy_api_key or 'fake_etsy_api_key_123'}" in url
    assert "state=" in url
    assert fake_redis.set.called


@pytest.mark.asyncio
async def test_handle_oauth_callback_success(
    mock_uow: MagicMock,
    fake_redis: AsyncMock,
    cipher: CredentialCipher,
    settings: Settings,
) -> None:
    owner_id = uuid.uuid4()
    state = "secure_random_state_123"
    verifier = "mock_pkce_verifier_string_456"

    await fake_redis.set(
        f"etsy:oauth_state:{state}",
        json.dumps({"owner_id": str(owner_id), "code_verifier": verifier}),
    )

    fake_gateway = FakeEtsyProvider(
        default_shop_id="shop_999",
        default_shop_name="ArtisanalPrints",
        default_user_id="user_888",
    )

    fake_conn = MagicMock(spec=ShopConnection)
    fake_conn.id = uuid.uuid4()
    fake_conn.user_id = owner_id
    fake_conn.etsy_shop_id = "shop_999"
    fake_conn.etsy_shop_name = "ArtisanalPrints"
    fake_conn.connection_status = "connected"
    fake_conn.is_connected = True
    fake_conn.ciphertext_access_token = cipher.encrypt("fake_access_token_123")
    fake_conn.key_version = cipher.key_version

    mock_uow.shop_connections.upsert = AsyncMock(return_value=fake_conn)

    conn = await handle_oauth_callback(
        uow=mock_uow,
        redis=fake_redis,
        cipher=cipher,
        etsy_gateway=fake_gateway,
        code="oauth_code_xyz",
        state=state,
        settings=settings,
    )

    assert conn.user_id == owner_id
    assert conn.etsy_shop_id == "shop_999"
    assert conn.etsy_shop_name == "ArtisanalPrints"
    assert conn.connection_status == "connected"

    # State must be consumed from Redis (single use)
    assert await fake_redis.get(f"etsy:oauth_state:{state}") is None
    assert mock_uow.audit.record.called


@pytest.mark.asyncio
async def test_handle_oauth_callback_invalid_state(
    mock_uow: MagicMock,
    fake_redis: AsyncMock,
    cipher: CredentialCipher,
    settings: Settings,
) -> None:
    fake_gateway = FakeEtsyProvider()
    with pytest.raises(ValueError, match="Invalid, expired, or already used"):
        await handle_oauth_callback(
            uow=mock_uow,
            redis=fake_redis,
            cipher=cipher,
            etsy_gateway=fake_gateway,
            code="code",
            state="non_existent_state",
            settings=settings,
        )


@pytest.mark.asyncio
async def test_get_valid_access_token_active(
    mock_uow: MagicMock,
    cipher: CredentialCipher,
) -> None:
    owner_id = uuid.uuid4()
    active_conn = MagicMock(spec=ShopConnection)
    active_conn.id = uuid.uuid4()
    active_conn.user_id = owner_id
    active_conn.connection_status = "connected"
    active_conn.key_version = cipher.key_version
    active_conn.ciphertext_access_token = cipher.encrypt("valid_token_now")
    active_conn.ciphertext_refresh_token = cipher.encrypt("refresh_token_1")
    active_conn.token_expires_at = datetime.now(UTC) + timedelta(hours=1)

    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=active_conn)

    fake_gateway = FakeEtsyProvider()
    token = await get_valid_access_token(mock_uow, cipher, fake_gateway, owner_id)
    assert token == "valid_token_now"
    assert len(fake_gateway.refreshed_tokens) == 0


@pytest.mark.asyncio
async def test_get_valid_access_token_auto_refreshes_when_expiring(
    mock_uow: MagicMock,
    cipher: CredentialCipher,
) -> None:
    owner_id = uuid.uuid4()
    expiring_conn = MagicMock(spec=ShopConnection)
    expiring_conn.id = uuid.uuid4()
    expiring_conn.user_id = owner_id
    expiring_conn.connection_status = "connected"
    expiring_conn.key_version = cipher.key_version
    expiring_conn.ciphertext_access_token = cipher.encrypt("almost_expired_token")
    expiring_conn.ciphertext_refresh_token = cipher.encrypt("valid_refresh_token_2")
    expiring_conn.token_expires_at = datetime.now(UTC) + timedelta(seconds=60)

    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=expiring_conn)
    mock_uow.shop_connections.update_tokens = AsyncMock()

    fake_gateway = FakeEtsyProvider()
    token = await get_valid_access_token(mock_uow, cipher, fake_gateway, owner_id)

    assert "refreshed_access_token" in token
    assert len(fake_gateway.refreshed_tokens) == 1
    assert mock_uow.shop_connections.update_tokens.called
    assert mock_uow.audit.record.called


@pytest.mark.asyncio
async def test_get_valid_access_token_revocation_handling(
    mock_uow: MagicMock,
    cipher: CredentialCipher,
) -> None:
    owner_id = uuid.uuid4()
    revoked_conn = MagicMock(spec=ShopConnection)
    revoked_conn.id = uuid.uuid4()
    revoked_conn.user_id = owner_id
    revoked_conn.connection_status = "connected"
    revoked_conn.key_version = cipher.key_version
    revoked_conn.ciphertext_access_token = cipher.encrypt("expired_token")
    revoked_conn.ciphertext_refresh_token = cipher.encrypt("revoked_refresh_token")
    revoked_conn.token_expires_at = datetime.now(UTC) - timedelta(minutes=10)

    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=revoked_conn)
    mock_uow.shop_connections.update_status = AsyncMock()

    fake_gateway = FakeEtsyProvider()
    fake_gateway.fail_refresh = True

    with pytest.raises(ReauthorizationRequiredError):
        await get_valid_access_token(mock_uow, cipher, fake_gateway, owner_id)

    assert mock_uow.shop_connections.update_status.called


@pytest.mark.asyncio
async def test_disconnect_etsy(
    mock_uow: MagicMock,
) -> None:
    owner_id = uuid.uuid4()
    existing_conn = MagicMock(spec=ShopConnection)
    existing_conn.id = uuid.uuid4()

    mock_uow.shop_connections.get_by_user_id = AsyncMock(return_value=existing_conn)
    mock_uow.shop_connections.delete = AsyncMock()

    await disconnect_etsy(mock_uow, owner_id)

    mock_uow.shop_connections.delete.assert_called_once_with(existing_conn)
    assert mock_uow.audit.record.called
