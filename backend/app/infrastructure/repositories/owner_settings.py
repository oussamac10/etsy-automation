"""Owner settings and provider credential repositories.

The credential repository takes and returns *ciphertext*. Encryption belongs to
the use case, which owns the cipher; a repository that encrypted would put a key
inside the persistence layer and make the boundary harder to reason about.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ProviderName
from app.infrastructure.models import OwnerSettings, ProviderCredential


class SqlOwnerSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, user_id: uuid.UUID) -> OwnerSettings | None:
        result = await self._session.execute(
            select(OwnerSettings).where(OwnerSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_defaults(self, user_id: uuid.UUID) -> OwnerSettings:
        """Materialise the defaults declared on the model.

        Settings are created lazily on first read rather than at signup, so an
        account created by a migration or a fixture cannot end up without a row.
        """
        settings = OwnerSettings(user_id=user_id)
        self._session.add(settings)
        await self._session.flush()
        return settings

    async def apply(self, settings: OwnerSettings, changes: dict[str, Any]) -> OwnerSettings:
        """Assign validated changes.

        The caller has already validated names and values at the API boundary;
        an unknown attribute here is a programming error, not user input, so it
        raises rather than being silently dropped.
        """
        for name, value in changes.items():
            if not hasattr(settings, name):
                raise AttributeError(f"OwnerSettings has no field {name!r}")
            setattr(settings, name, value)
        await self._session.flush()
        return settings


class SqlProviderCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID, provider: ProviderName) -> ProviderCredential | None:
        result = await self._session.execute(
            select(ProviderCredential).where(
                ProviderCredential.user_id == user_id,
                ProviderCredential.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[ProviderCredential]:
        result = await self._session.execute(
            select(ProviderCredential)
            .where(ProviderCredential.user_id == user_id)
            .order_by(ProviderCredential.provider)
        )
        return result.scalars().all()

    async def list_stale_key_versions(self, current_version: int) -> Sequence[ProviderCredential]:
        """Every credential not yet written under the current key.

        Cross-owner on purpose: key rotation is an operator action over the whole
        table, not something one owner does to their own rows.
        """
        result = await self._session.execute(
            select(ProviderCredential).where(ProviderCredential.key_version != current_version)
        )
        return result.scalars().all()

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        provider: ProviderName,
        ciphertext: bytes,
        key_version: int,
        masked_value: str,
        label: str | None = None,
    ) -> tuple[ProviderCredential, bool]:
        """Store or replace a credential. Returns ``(credential, created)``.

        Replacement overwrites the ciphertext in place: two rows for one
        provider would leave a stale secret decryptable beside its replacement.
        """
        existing = await self.get(user_id, provider)
        if existing is not None:
            existing.ciphertext = ciphertext
            existing.key_version = key_version
            existing.masked_value = masked_value
            existing.label = label
            await self._session.flush()
            return existing, False

        credential = ProviderCredential(
            user_id=user_id,
            provider=provider,
            ciphertext=ciphertext,
            key_version=key_version,
            masked_value=masked_value,
            label=label,
        )
        self._session.add(credential)
        await self._session.flush()
        return credential, True

    async def delete(self, credential: ProviderCredential) -> None:
        """A credential is not audit data; the audit event records the removal."""
        await self._session.delete(credential)
        await self._session.flush()
