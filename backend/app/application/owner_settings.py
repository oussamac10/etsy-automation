"""Settings and provider-credential use cases.

Everything here is scoped to one authenticated owner. No function accepts an
owner ID from a request body: the caller passes the identity the session
resolved to, which is why cross-owner access is not a check that can be
forgotten at a route.

A decrypted credential never leaves this module through a return value. The one
function that decrypts (:func:`reveal_credential`) exists for the provider
adapters that arrive in Phase 5 and is not wired to any route.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction, ProviderName
from app.domain.errors import CredentialConfigurationError, EntityNotFoundError
from app.infrastructure.models import OwnerSettings, ProviderCredential
from app.infrastructure.security import (
    CredentialCipher,
    CredentialDecryptionError,
    EncryptionConfigurationError,
    mask_secret,
)


@dataclass(frozen=True, slots=True)
class CredentialSummary:
    """The only shape a credential may take outside this module."""

    provider: ProviderName
    configured: bool
    masked_value: str | None
    label: str | None
    key_version: int | None
    updated_at: str | None


async def get_or_create_settings(uow: UnitOfWork, owner_id: uuid.UUID) -> OwnerSettings:
    """Read the owner's settings, materialising the defaults on first access.

    Creating lazily rather than at account creation means an account made by a
    migration, a fixture or the bootstrap command can never be missing a row.
    """
    settings = await uow.owner_settings.get_for_user(owner_id)
    if settings is not None:
        return settings

    settings = await uow.owner_settings.create_defaults(owner_id)
    await uow.commit()
    return settings


async def update_settings(
    uow: UnitOfWork,
    owner_id: uuid.UUID,
    changes: dict[str, Any],
) -> OwnerSettings:
    """Apply a validated partial update.

    ``changes`` contains only the fields the request actually sent, already
    validated and bounded by the API schema. An empty change set is a no-op that
    still returns the current settings rather than an error, so a form that
    submits nothing is not a failure.
    """
    settings = await get_or_create_settings(uow, owner_id)
    if not changes:
        return settings

    before = {name: _auditable(getattr(settings, name)) for name in changes}
    await uow.owner_settings.apply(settings, changes)
    await uow.audit.record(
        action=AuditAction.SETTINGS_UPDATED,
        entity_type="OwnerSettings",
        entity_id=settings.id,
        actor=str(owner_id),
        summary=f"Settings updated: {', '.join(sorted(changes))}",
        before=before,
        after={name: _auditable(value) for name, value in changes.items()},
    )
    await uow.commit()
    return settings


async def list_credentials(uow: UnitOfWork, owner_id: uuid.UUID) -> list[CredentialSummary]:
    """Every supported provider, configured or not.

    Returning the unconfigured ones too means the UI does not have to know the
    provider list, and "not configured" is an explicit state rather than an
    absence the client has to infer.
    """
    stored = {
        credential.provider: credential
        for credential in await uow.credentials.list_for_user(owner_id)
    }
    return [_summarise(provider, stored.get(provider)) for provider in ProviderName]


async def store_credential(
    uow: UnitOfWork,
    owner_id: uuid.UUID,
    *,
    provider: ProviderName,
    secret: str,
    label: str | None,
    cipher: CredentialCipher | None,
) -> CredentialSummary:
    """Encrypt and store a provider secret, replacing any existing one.

    ``cipher`` is ``None`` when the encryption key is missing or unusable. That
    is a 503, not a 500: refusing to store is the safe failure, and storing
    plaintext to "keep working" would be the unsafe one.
    """
    active = _require_cipher(cipher)
    try:
        ciphertext = active.encrypt(secret)
    except (EncryptionConfigurationError, ValueError) as exc:
        raise CredentialConfigurationError(str(exc)) from exc

    credential, created = await uow.credentials.upsert(
        user_id=owner_id,
        provider=provider,
        ciphertext=ciphertext,
        key_version=active.key_version,
        masked_value=mask_secret(secret),
        label=label,
    )
    await uow.audit.record(
        action=AuditAction.CREDENTIAL_STORED,
        entity_type="ProviderCredential",
        entity_id=credential.id,
        actor=str(owner_id),
        summary=f"{provider} credential {'stored' if created else 'replaced'}",
        # The masked value is recorded so the audit trail can show *which* key
        # was swapped. The secret and the ciphertext are not.
        after={"provider": provider.value, "masked": credential.masked_value},
    )
    await uow.commit()
    return _summarise(provider, credential)


async def delete_credential(
    uow: UnitOfWork, owner_id: uuid.UUID, *, provider: ProviderName
) -> None:
    """Remove a stored secret. 404 when this owner has none for the provider."""
    credential = await uow.credentials.get(owner_id, provider)
    if credential is None:
        raise EntityNotFoundError("ProviderCredential", provider.value)

    masked = credential.masked_value
    await uow.credentials.delete(credential)
    await uow.audit.record(
        action=AuditAction.CREDENTIAL_DELETED,
        entity_type="ProviderCredential",
        actor=str(owner_id),
        summary=f"{provider} credential deleted",
        before={"provider": provider.value, "masked": masked},
    )
    await uow.commit()


async def reveal_credential(
    uow: UnitOfWork,
    owner_id: uuid.UUID,
    *,
    provider: ProviderName,
    cipher: CredentialCipher | None,
) -> str:
    """Decrypt a stored secret for a provider call.

    Deliberately not reachable from any route. Phase 5 adapters call this when
    they are about to make a request; nothing else should.
    """
    active = _require_cipher(cipher)
    credential = await uow.credentials.get(owner_id, provider)
    if credential is None:
        raise EntityNotFoundError("ProviderCredential", provider.value)
    try:
        return active.decrypt(credential.ciphertext, key_version=credential.key_version)
    except CredentialDecryptionError as exc:
        raise CredentialConfigurationError(str(exc)) from exc


async def rotate_credential_keys(uow: UnitOfWork, *, cipher: CredentialCipher | None) -> int:
    """Re-encrypt every stale credential under the current key. Returns the count.

    An operator action, not an owner action, so it takes no owner ID. It is
    re-runnable: a row already at the current version is skipped, and the whole
    pass commits once, so a failure part-way leaves nothing half-rotated.
    """
    active = _require_cipher(cipher)
    stale = await uow.credentials.list_stale_key_versions(active.key_version)
    for credential in stale:
        try:
            plaintext = active.decrypt(credential.ciphertext, key_version=credential.key_version)
        except CredentialDecryptionError as exc:
            raise CredentialConfigurationError(
                f"credential {credential.id} cannot be read with the configured keys; "
                "set ENCRYPTION_KEY_PREVIOUS to the retired key before rotating"
            ) from exc
        credential.ciphertext = active.encrypt(plaintext)
        credential.key_version = active.key_version
    if stale:
        await uow.commit()
    return len(stale)


def _require_cipher(cipher: CredentialCipher | None) -> CredentialCipher:
    if cipher is None:
        raise CredentialConfigurationError(
            "Credential encryption is not configured; ENCRYPTION_KEY is missing or invalid."
        )
    return cipher


def _summarise(provider: ProviderName, credential: ProviderCredential | None) -> CredentialSummary:
    if credential is None:
        return CredentialSummary(
            provider=provider,
            configured=False,
            masked_value=None,
            label=None,
            key_version=None,
            updated_at=None,
        )
    return CredentialSummary(
        provider=provider,
        configured=True,
        masked_value=credential.masked_value,
        label=credential.label,
        key_version=credential.key_version,
        updated_at=credential.updated_at.isoformat(),
    )


def _auditable(value: object) -> object:
    """JSON-safe rendering for the audit payload. Settings hold no secrets."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, bool | int | str) or value is None:
        return value
    return str(value)
