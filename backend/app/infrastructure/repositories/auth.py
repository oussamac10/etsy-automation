"""Session repository.

Lookups are by *token hash* only. The repository never sees a plaintext token,
which keeps the hashing decision in one place (``app/infrastructure/security``)
instead of at every call site.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.models import UserSession


class SqlSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        csrf_token: str,
        expires_at: datetime,
        user_agent: str | None = None,
    ) -> UserSession:
        record = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            csrf_token=csrf_token,
            expires_at=expires_at,
            user_agent=user_agent,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        """The session and its user in one query.

        Every authenticated request needs both, so eager-loading the user here
        avoids a second round trip on the hot path.
        """
        result = await self._session.execute(
            select(UserSession)
            .where(UserSession.token_hash == token_hash)
            .options(selectinload(UserSession.user))
        )
        return result.scalar_one_or_none()

    async def touch(self, record: UserSession, *, now: datetime) -> None:
        record.last_seen_at = now

    async def revoke(self, record: UserSession, *, now: datetime) -> None:
        """Idempotent: revoking an already-revoked session keeps the first time."""
        if record.revoked_at is None:
            record.revoked_at = now

    async def revoke_all_for_user(self, user_id: uuid.UUID, *, now: datetime) -> int:
        """Revoke every live session for one user. Returns how many were live.

        The lever that makes a server-side session worth its table: one write
        ends every browser, which a stateless token cannot offer.
        """
        result = await self._session.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def active_for_user(self, user_id: uuid.UUID, *, now: datetime) -> Sequence[UserSession]:
        result = await self._session.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        )
        return result.scalars().all()
