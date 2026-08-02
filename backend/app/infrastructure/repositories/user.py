"""User repository.

Takes and returns *hashes*, never a password. Hashing lives in
``app/infrastructure/security``; keeping it out of here means there is exactly
one place that decides the algorithm and its parameters.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import User


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str | None = None,
        is_active: bool = True,
        user_id: uuid.UUID | None = None,
    ) -> User:
        user = User(
            email=_normalize_email(email),
            display_name=display_name,
            password_hash=password_hash,
            is_active=is_active,
        )
        if user_id is not None:
            # Only fixtures pass an ID; everything else takes the generated one.
            user.id = user_id
        self._session.add(user)
        await self._session.flush()
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Case-insensitive lookup.

        Addresses are stored normalised, but a row written before that rule (or
        by hand) must still be found, so the comparison lowers both sides.
        """
        result = await self._session.execute(
            select(User).where(func.lower(User.email) == _normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def set_password_hash(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        await self._session.flush()
        return user


def _normalize_email(email: str) -> str:
    return email.strip().lower()
