from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.telegram import TelegramConnection
from app.ports.repositories import TelegramConnectionRepository


class SqlTelegramConnectionRepository(TelegramConnectionRepository):
    """PostgreSQL implementation of the TelegramConnectionRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> TelegramConnection | None:
        stmt = select(TelegramConnection).where(TelegramConnection.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> TelegramConnection | None:
        stmt = select(TelegramConnection).where(
            TelegramConnection.telegram_user_id == telegram_user_id,
            TelegramConnection.revoked_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update_pairing_code(
        self,
        *,
        user_id: uuid.UUID,
        code_hash: str,
        expires_at: datetime,
    ) -> TelegramConnection:
        record = await self.get_by_user_id(user_id)
        if record is None:
            record = TelegramConnection(
                user_id=user_id,
                pairing_code_hash=code_hash,
                pairing_code_expires_at=expires_at,
                failed_pairing_attempts=0,
            )
            self._session.add(record)
        else:
            record.pairing_code_hash = code_hash
            record.pairing_code_expires_at = expires_at
            record.failed_pairing_attempts = 0
            record.revoked_at = None
            record.paired_at = None
            record.telegram_user_id = None
            record.telegram_chat_id = None
            record.telegram_username = None

        return record

    async def get_by_pairing_code_hash(self, code_hash: str) -> TelegramConnection | None:
        stmt = select(TelegramConnection).where(
            TelegramConnection.pairing_code_hash == code_hash,
            TelegramConnection.telegram_user_id.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_failed_attempts(self, record: TelegramConnection) -> None:
        record.failed_pairing_attempts += 1
        if record.failed_pairing_attempts >= 3:
            record.pairing_code_expires_at = None
            record.pairing_code_hash = None

    async def pair(
        self,
        record: TelegramConnection,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_username: str | None,
        paired_at: datetime,
    ) -> None:
        record.telegram_user_id = telegram_user_id
        record.telegram_chat_id = telegram_chat_id
        record.telegram_username = telegram_username
        record.paired_at = paired_at
        record.pairing_code_hash = None
        record.pairing_code_expires_at = None
        record.failed_pairing_attempts = 0
        record.revoked_at = None

    async def disconnect(self, record: TelegramConnection, *, revoked_at: datetime) -> None:
        record.revoked_at = revoked_at
        record.telegram_user_id = None
        record.telegram_chat_id = None
        record.telegram_username = None
        record.paired_at = None
        record.pairing_code_hash = None
        record.pairing_code_expires_at = None
        record.failed_pairing_attempts = 0
