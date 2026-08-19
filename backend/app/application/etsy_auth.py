"""Etsy OAuth 2.0 PKCE authentication and token refresh application service."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.domain.errors import DomainError, EntityNotFoundError
from app.infrastructure.models import ShopConnection
from app.infrastructure.security import CredentialCipher
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import EtsyGateway
from app.settings import Settings


class ReauthorizationRequiredError(DomainError):
    """Raised when Etsy OAuth refresh token is invalid or revoked."""

    def __init__(self, message: str = "Etsy authorization has expired or been revoked.") -> None:
        super().__init__(message)


def generate_pkce_pair() -> tuple[str, str]:
    """Generate high-entropy PKCE code_verifier and S256 code_challenge.

    Complies with RFC 7636:
    - code_verifier: 43-128 unreserved URL-safe characters
    - code_challenge: BASE64URL-ENCODE(SHA256(code_verifier)) without padding
    """
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


async def create_oauth_connect_url(
    redis: aioredis.Redis,
    owner_id: uuid.UUID,
    settings: Settings,
) -> str:
    """Generate Etsy PKCE OAuth authorization URL and store temporary state in Redis."""
    api_key = settings.resolved_etsy_api_key
    if not api_key:
        if settings.provider_mode == "fake":
            api_key = "fake_etsy_api_key_123"
        else:
            raise ValueError(
                "Etsy API Key is not configured on the server. "
                "Please set ETSY_API_KEY (or ETSY_CLIENT_ID) in your .env file."
            )

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()

    state_payload = {
        "owner_id": str(owner_id),
        "code_verifier": code_verifier,
        "created_at": datetime.now(UTC).isoformat(),
    }

    # Store state with a 10-minute TTL in Redis
    redis_key = f"etsy:oauth_state:{state}"
    await redis.set(redis_key, json.dumps(state_payload), ex=600)

    params = {
        "response_type": "code",
        "client_id": api_key,
        "redirect_uri": settings.etsy_redirect_uri,
        "scope": settings.etsy_scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    query_string = urllib.parse.urlencode(params)
    return f"{settings.etsy_authorization_url}?{query_string}"


async def handle_oauth_callback(
    uow: UnitOfWork,
    redis: aioredis.Redis,
    cipher: CredentialCipher,
    etsy_gateway: EtsyGateway,
    code: str,
    state: str,
    settings: Settings,
) -> ShopConnection:
    """Validate OAuth state, exchange code for tokens, fetch shop profile, and persist encrypted ShopConnection."""
    redis_key = f"etsy:oauth_state:{state}"
    raw_state = await redis.get(redis_key)
    if not raw_state:
        raise ValueError("Invalid, expired, or already used Etsy OAuth state.")

    # Consume immediately to enforce single-use
    await redis.delete(redis_key)

    state_data: dict[str, Any] = json.loads(raw_state)
    owner_id = uuid.UUID(state_data["owner_id"])
    code_verifier = state_data["code_verifier"]

    # Exchange code for tokens
    token_resp = await etsy_gateway.exchange_code_for_token(
        code=code,
        code_verifier=code_verifier,
        redirect_uri=settings.etsy_redirect_uri,
    )

    # Fetch user and shop details
    user_info = await etsy_gateway.get_me(access_token=token_resp.access_token)
    shops = await etsy_gateway.get_user_shops(
        access_token=token_resp.access_token, user_id=user_info.user_id
    )
    if not shops:
        raise ValueError(
            "No active Etsy shops found for this account. Please create an Etsy shop before connecting."
        )

    primary_shop = shops[0]

    # Encrypt tokens with current key version
    ciphertext_access = cipher.encrypt(token_resp.access_token)
    ciphertext_refresh = cipher.encrypt(token_resp.refresh_token)

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=token_resp.expires_in)

    conn = await uow.shop_connections.upsert(
        user_id=owner_id,
        provider="etsy",
        etsy_user_id=user_info.user_id,
        etsy_shop_id=primary_shop.shop_id,
        etsy_shop_name=primary_shop.shop_name,
        ciphertext_access_token=ciphertext_access,
        ciphertext_refresh_token=ciphertext_refresh,
        key_version=cipher.key_version,
        token_expires_at=expires_at,
        granted_scopes=token_resp.scope,
        connection_status="connected",
        last_refreshed_at=now,
    )

    await uow.audit.record(
        action=AuditAction.ETSY_CONNECTED,
        entity_type="ShopConnection",
        entity_id=conn.id,
        actor=str(owner_id),
        summary=f"Etsy shop '{primary_shop.shop_name}' (ID: {primary_shop.shop_id}) successfully connected.",
        metadata={
            "etsy_shop_id": primary_shop.shop_id,
            "etsy_shop_name": primary_shop.shop_name,
            "granted_scopes": token_resp.scope,
        },
    )

    return conn


async def get_valid_access_token(
    uow: UnitOfWork,
    cipher: CredentialCipher,
    etsy_gateway: EtsyGateway,
    owner_id: uuid.UUID,
    min_ttl_seconds: int = 300,
) -> str:
    """Retrieve decrypted access token, automatically refreshing if close to expiration."""
    conn = await uow.shop_connections.get_by_user_id(owner_id)
    if conn is None or conn.connection_status == "disconnected":
        raise EntityNotFoundError("ShopConnection", owner_id)

    now = datetime.now(UTC)
    needs_refresh = (conn.token_expires_at - now).total_seconds() < min_ttl_seconds

    if needs_refresh:
        # Decrypt refresh token
        plain_refresh = cipher.decrypt(
            conn.ciphertext_refresh_token, key_version=conn.key_version
        )

        try:
            token_resp = await etsy_gateway.refresh_token(refresh_token=plain_refresh)
        except ProviderError as exc:
            if exc.kind == ProviderErrorKind.AUTHENTICATION:
                await uow.shop_connections.update_status(
                    conn, connection_status="reauthorization_required"
                )
                await uow.audit.record(
                    action=AuditAction.ETSY_TOKEN_REFRESHED,
                    entity_type="ShopConnection",
                    entity_id=conn.id,
                    actor=str(owner_id),
                    summary="Etsy token refresh failed: reauthorization required.",
                    metadata={"error": str(exc)},
                )
                raise ReauthorizationRequiredError(
                    "Etsy authorization has expired or been revoked. Please reconnect your Etsy shop."
                ) from exc
            raise

        new_ciphertext_access = cipher.encrypt(token_resp.access_token)
        new_ciphertext_refresh = cipher.encrypt(token_resp.refresh_token)
        new_expires_at = now + timedelta(seconds=token_resp.expires_in)

        await uow.shop_connections.update_tokens(
            conn,
            ciphertext_access_token=new_ciphertext_access,
            ciphertext_refresh_token=new_ciphertext_refresh,
            key_version=cipher.key_version,
            token_expires_at=new_expires_at,
            last_refreshed_at=now,
        )

        await uow.audit.record(
            action=AuditAction.ETSY_TOKEN_REFRESHED,
            entity_type="ShopConnection",
            entity_id=conn.id,
            actor=str(owner_id),
            summary="Etsy OAuth access token refreshed automatically.",
            metadata={"expires_at": new_expires_at.isoformat()},
        )

        return token_resp.access_token

    # Return active decrypted access token
    return cipher.decrypt(conn.ciphertext_access_token, key_version=conn.key_version)


async def disconnect_etsy(uow: UnitOfWork, owner_id: uuid.UUID) -> None:
    """Disconnect and revoke local Etsy shop authorization."""
    conn = await uow.shop_connections.get_by_user_id(owner_id)
    if conn is not None:
        await uow.shop_connections.delete(conn)
        await uow.audit.record(
            action=AuditAction.ETSY_DISCONNECTED,
            entity_type="ShopConnection",
            entity_id=conn.id,
            actor=str(owner_id),
            summary="Etsy shop disconnected by owner.",
        )
