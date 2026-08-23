"""SQLAlchemy repository for ShopConnection entities."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import ShopConnection
from app.ports.repositories import ShopConnectionRepository


class SqlShopConnectionRepository(ShopConnectionRepository):
    """PostgreSQL implementation of ShopConnectionRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(
        self, user_id: uuid.UUID, provider: str = "etsy"
    ) -> ShopConnection | None:
        stmt = select(ShopConnection).where(
            ShopConnection.user_id == user_id,
            ShopConnection.provider == provider,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_shop_id(
        self, etsy_shop_id: str, provider: str = "etsy"
    ) -> ShopConnection | None:
        stmt = select(ShopConnection).where(
            ShopConnection.etsy_shop_id == etsy_shop_id,
            ShopConnection.provider == provider,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[ShopConnection]:
        stmt = select(ShopConnection).where(ShopConnection.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        provider: str = "etsy",
        etsy_user_id: str,
        etsy_shop_id: str,
        etsy_shop_name: str,
        ciphertext_access_token: bytes,
        ciphertext_refresh_token: bytes,
        key_version: int,
        token_expires_at: datetime,
        granted_scopes: list[str],
        connection_status: str = "connected",
        last_refreshed_at: datetime | None = None,
    ) -> ShopConnection:
        record = await self.get_by_user_id(user_id, provider=provider)
        if record is None:
            record = ShopConnection(
                user_id=user_id,
                provider=provider,
                etsy_user_id=etsy_user_id,
                etsy_shop_id=etsy_shop_id,
                etsy_shop_name=etsy_shop_name,
                ciphertext_access_token=ciphertext_access_token,
                ciphertext_refresh_token=ciphertext_refresh_token,
                key_version=key_version,
                token_expires_at=token_expires_at,
                granted_scopes=granted_scopes,
                connection_status=connection_status,
                last_refreshed_at=last_refreshed_at,
            )
            self._session.add(record)
        else:
            record.etsy_user_id = etsy_user_id
            record.etsy_shop_id = etsy_shop_id
            record.etsy_shop_name = etsy_shop_name
            record.ciphertext_access_token = ciphertext_access_token
            record.ciphertext_refresh_token = ciphertext_refresh_token
            record.key_version = key_version
            record.token_expires_at = token_expires_at
            record.granted_scopes = granted_scopes
            record.connection_status = connection_status
            if last_refreshed_at is not None:
                record.last_refreshed_at = last_refreshed_at

        await self._session.flush()
        return record

    async def update_tokens(
        self,
        record: ShopConnection,
        *,
        ciphertext_access_token: bytes,
        ciphertext_refresh_token: bytes,
        key_version: int,
        token_expires_at: datetime,
        last_refreshed_at: datetime | None = None,
    ) -> ShopConnection:
        record.ciphertext_access_token = ciphertext_access_token
        record.ciphertext_refresh_token = ciphertext_refresh_token
        record.key_version = key_version
        record.token_expires_at = token_expires_at
        record.connection_status = "connected"
        record.last_refreshed_at = last_refreshed_at or datetime.now(UTC)
        await self._session.flush()
        return record

    async def update_status(
        self, record: ShopConnection, *, connection_status: str
    ) -> ShopConnection:
        record.connection_status = connection_status
        await self._session.flush()
        return record

    async def delete(self, record: ShopConnection) -> None:
        await self._session.delete(record)
        await self._session.flush()
