"""Phase 3 repositories and the database constraints behind them.

The constraint tests are here rather than in the unit suite on purpose: a CHECK
or a unique index only exists in PostgreSQL, so only PostgreSQL can prove the
migration actually created it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.owner_settings import rotate_credential_keys
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ProviderName
from app.domain.errors import CredentialConfigurationError
from app.infrastructure.models import OwnerSettings, ProviderCredential, User, UserSession
from app.infrastructure.security import CredentialCipher, mask_secret

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
async def user(uow: UnitOfWork) -> User:
    record = await uow.users.add(email="repo-owner@example.invalid", display_name="Repo Owner")
    await uow.commit()
    return record


@pytest.fixture
async def other_user(uow: UnitOfWork, user: User) -> User:
    record = await uow.users.add(email="repo-other@example.invalid", display_name="Other")
    await uow.commit()
    return record


class TestSessionRepository:
    async def test_a_session_is_found_by_its_hash_with_the_user_attached(
        self, uow: UnitOfWork, user: User
    ) -> None:
        await uow.sessions.create(
            user_id=user.id,
            token_hash="hash-1",
            csrf_token="csrf-1",
            expires_at=_now() + timedelta(hours=1),
        )
        await uow.commit()

        found = await uow.sessions.get_by_token_hash("hash-1")
        assert found is not None
        assert found.user.id == user.id
        assert found.revoked_at is None

    async def test_an_unknown_hash_is_none_not_an_error(self, uow: UnitOfWork) -> None:
        assert await uow.sessions.get_by_token_hash("nope") is None

    async def test_revoking_is_idempotent_and_keeps_the_first_time(
        self, uow: UnitOfWork, user: User
    ) -> None:
        record = await uow.sessions.create(
            user_id=user.id,
            token_hash="hash-2",
            csrf_token="csrf-2",
            expires_at=_now() + timedelta(hours=1),
        )
        first = _now()
        await uow.sessions.revoke(record, now=first)
        await uow.sessions.revoke(record, now=first + timedelta(minutes=5))
        assert record.revoked_at == first

    async def test_revoke_all_ends_only_this_users_live_sessions(
        self, uow: UnitOfWork, user: User, other_user: User
    ) -> None:
        expiry = _now() + timedelta(hours=1)
        for index in range(2):
            await uow.sessions.create(
                user_id=user.id,
                token_hash=f"mine-{index}",
                csrf_token="c",
                expires_at=expiry,
            )
        theirs = await uow.sessions.create(
            user_id=other_user.id, token_hash="theirs", csrf_token="c", expires_at=expiry
        )
        await uow.commit()

        assert await uow.sessions.revoke_all_for_user(user.id, now=_now()) == 2
        # Nothing left to revoke the second time.
        assert await uow.sessions.revoke_all_for_user(user.id, now=_now()) == 0
        await uow.commit()

        await uow.session.refresh(theirs)
        assert theirs.revoked_at is None
        assert await uow.sessions.active_for_user(user.id, now=_now()) == []

    async def test_active_ignores_expired_and_revoked(self, uow: UnitOfWork, user: User) -> None:
        now = _now()
        await uow.sessions.create(
            user_id=user.id, token_hash="live", csrf_token="c", expires_at=now + timedelta(hours=1)
        )
        revoked = await uow.sessions.create(
            user_id=user.id,
            token_hash="dead",
            csrf_token="c",
            expires_at=now + timedelta(hours=1),
        )
        await uow.sessions.revoke(revoked, now=now)
        await uow.commit()

        active = await uow.sessions.active_for_user(user.id, now=now)
        assert [record.token_hash for record in active] == ["live"]

        # And a session whose expiry has passed drops out without being revoked.
        assert await uow.sessions.active_for_user(user.id, now=now + timedelta(hours=2)) == []


class TestSessionConstraints:
    async def test_a_token_hash_is_unique(self, uow: UnitOfWork, user: User) -> None:
        expiry = _now() + timedelta(hours=1)
        await uow.sessions.create(
            user_id=user.id, token_hash="same", csrf_token="c", expires_at=expiry
        )
        await uow.commit()
        with pytest.raises(IntegrityError):
            await uow.sessions.create(
                user_id=user.id, token_hash="same", csrf_token="c", expires_at=expiry
            )
            await uow.commit()

    async def test_an_expiry_before_creation_is_refused(self, uow: UnitOfWork, user: User) -> None:
        with pytest.raises(IntegrityError, match="expiry_after_creation"):
            await uow.sessions.create(
                user_id=user.id,
                token_hash="backdated",
                csrf_token="c",
                expires_at=_now() - timedelta(hours=1),
            )
            await uow.commit()

    async def test_deleting_a_user_deletes_their_sessions(
        self, uow: UnitOfWork, user: User
    ) -> None:
        await uow.sessions.create(
            user_id=user.id,
            token_hash="cascade",
            csrf_token="c",
            expires_at=_now() + timedelta(hours=1),
        )
        await uow.commit()

        await uow.session.execute(sqlalchemy.delete(User).where(User.id == user.id))
        await uow.commit()

        remaining = await uow.session.scalar(
            sqlalchemy.select(sqlalchemy.func.count()).select_from(UserSession)
        )
        assert remaining == 0


class TestOwnerSettingsRepository:
    async def test_defaults_are_created_once_per_user(self, uow: UnitOfWork, user: User) -> None:
        assert await uow.owner_settings.get_for_user(user.id) is None
        created = await uow.owner_settings.create_defaults(user.id)
        await uow.commit()

        assert created.currency == "USD"
        assert (await uow.owner_settings.get_for_user(user.id)) is not None

    async def test_one_settings_row_per_user(self, uow: UnitOfWork, user: User) -> None:
        await uow.owner_settings.create_defaults(user.id)
        await uow.commit()
        with pytest.raises(IntegrityError):
            await uow.owner_settings.create_defaults(user.id)
            await uow.commit()

    async def test_apply_assigns_only_known_fields(self, uow: UnitOfWork, user: User) -> None:
        settings = await uow.owner_settings.create_defaults(user.id)
        await uow.owner_settings.apply(settings, {"target_country": "GB"})
        assert settings.target_country == "GB"

        with pytest.raises(AttributeError):
            await uow.owner_settings.apply(settings, {"not_a_field": 1})

    async def test_a_daily_budget_above_the_monthly_one_is_refused_by_the_database(
        self, uow: UnitOfWork, user: User
    ) -> None:
        """The API validates it too; the constraint is the backstop."""
        settings = await uow.owner_settings.create_defaults(user.id)
        await uow.commit()
        settings.daily_budget_minor = settings.monthly_budget_minor + 1
        with pytest.raises(IntegrityError, match="daily_within_monthly"):
            await uow.commit()

    async def test_a_negative_budget_is_refused_by_the_database(
        self, uow: UnitOfWork, user: User
    ) -> None:
        settings = await uow.owner_settings.create_defaults(user.id)
        await uow.commit()
        settings.daily_budget_minor = -1
        with pytest.raises(IntegrityError):
            await uow.commit()


class TestProviderCredentialRepository:
    async def test_upsert_creates_then_replaces_in_place(self, uow: UnitOfWork, user: User) -> None:
        credential, created = await uow.credentials.upsert(
            user_id=user.id,
            provider=ProviderName.OPENAI,
            ciphertext=b"first",
            key_version=1,
            masked_value="••••abcd",
        )
        await uow.commit()
        assert created is True

        replaced, created_again = await uow.credentials.upsert(
            user_id=user.id,
            provider=ProviderName.OPENAI,
            ciphertext=b"second",
            key_version=2,
            masked_value="••••wxyz",
            label="rotated",
        )
        await uow.commit()

        assert created_again is False
        assert replaced.id == credential.id
        assert replaced.ciphertext == b"second"
        assert replaced.key_version == 2
        assert replaced.label == "rotated"
        assert len(await uow.credentials.list_for_user(user.id)) == 1

    async def test_credentials_are_scoped_to_their_owner(
        self, uow: UnitOfWork, user: User, other_user: User
    ) -> None:
        await uow.credentials.upsert(
            user_id=user.id,
            provider=ProviderName.OPENAI,
            ciphertext=b"mine",
            key_version=1,
            masked_value="••••mine",
        )
        await uow.commit()

        assert await uow.credentials.get(other_user.id, ProviderName.OPENAI) is None
        assert await uow.credentials.list_for_user(other_user.id) == []

    async def test_deleting_removes_the_row(self, uow: UnitOfWork, user: User) -> None:
        credential, _ = await uow.credentials.upsert(
            user_id=user.id,
            provider=ProviderName.OPENAI,
            ciphertext=b"gone",
            key_version=1,
            masked_value="••••gone",
        )
        await uow.commit()
        await uow.credentials.delete(credential)
        await uow.commit()
        assert await uow.credentials.get(user.id, ProviderName.OPENAI) is None


class TestKeyRotation:
    """`ENCRYPTION_KEY` can be replaced without losing a stored secret."""

    OLD_KEY = "the-retired-application-key-01234567890"
    NEW_KEY = "the-current-application-key-01234567890"
    SECRET = "sk-provider-secret-to-carry-across"

    async def _store_under_old_key(self, uow: UnitOfWork, user: User) -> None:
        old = CredentialCipher(self.OLD_KEY, key_version=1)
        await uow.credentials.upsert(
            user_id=user.id,
            provider=ProviderName.OPENAI,
            ciphertext=old.encrypt(self.SECRET),
            key_version=1,
            masked_value=mask_secret(self.SECRET),
        )
        await uow.commit()

    def _rotating_cipher(self) -> CredentialCipher:
        return CredentialCipher(
            self.NEW_KEY, key_version=2, previous_key=self.OLD_KEY, previous_key_version=1
        )

    async def test_rotation_re_encrypts_and_the_secret_survives(
        self, uow: UnitOfWork, user: User
    ) -> None:
        await self._store_under_old_key(uow, user)
        cipher = self._rotating_cipher()

        assert await rotate_credential_keys(uow, cipher=cipher) == 1

        credential = await uow.credentials.get(user.id, ProviderName.OPENAI)
        assert credential is not None
        assert credential.key_version == 2
        # Readable under the new key alone: the retired key is now removable.
        new_only = CredentialCipher(self.NEW_KEY, key_version=2)
        assert new_only.decrypt(credential.ciphertext, key_version=2) == self.SECRET

    async def test_rotation_is_re_runnable(self, uow: UnitOfWork, user: User) -> None:
        await self._store_under_old_key(uow, user)
        cipher = self._rotating_cipher()
        assert await rotate_credential_keys(uow, cipher=cipher) == 1
        assert await rotate_credential_keys(uow, cipher=cipher) == 0

    async def test_rotating_without_the_retired_key_refuses_rather_than_destroys(
        self, uow: UnitOfWork, user: User
    ) -> None:
        await self._store_under_old_key(uow, user)
        user_id = user.id
        with pytest.raises(CredentialConfigurationError, match="ENCRYPTION_KEY_PREVIOUS"):
            await rotate_credential_keys(uow, cipher=CredentialCipher(self.NEW_KEY, key_version=2))

        await uow.rollback()
        credential = await uow.credentials.get(user_id, ProviderName.OPENAI)
        assert credential is not None
        assert credential.key_version == 1
        old = CredentialCipher(self.OLD_KEY, key_version=1)
        assert old.decrypt(credential.ciphertext, key_version=1) == self.SECRET

    async def test_rotation_without_a_cipher_is_a_configuration_error(
        self, uow: UnitOfWork
    ) -> None:
        with pytest.raises(CredentialConfigurationError, match="ENCRYPTION_KEY"):
            await rotate_credential_keys(uow, cipher=None)


class TestProviderCredentialConstraints:
    async def test_one_row_per_user_and_provider(self, uow: UnitOfWork, user: User) -> None:
        """Bypassing the repository must still hit the unique index."""
        for _ in range(2):
            uow.session.add(
                ProviderCredential(
                    user_id=user.id,
                    provider=ProviderName.OPENAI,
                    ciphertext=b"x",
                    key_version=1,
                    masked_value="••••x",
                )
            )
        with pytest.raises(IntegrityError, match="uq_provider_credentials_user_provider"):
            await uow.commit()

    @pytest.mark.parametrize(
        ("field", "value", "constraint"),
        [
            ("key_version", 0, "key_version_positive"),
            ("ciphertext", b"", "ciphertext_not_empty"),
        ],
    )
    async def test_invalid_ciphertext_rows_are_refused(
        self, uow: UnitOfWork, user: User, field: str, value: object, constraint: str
    ) -> None:
        credential = ProviderCredential(
            user_id=user.id,
            provider=ProviderName.OPENAI,
            ciphertext=b"x",
            key_version=1,
            masked_value="••••x",
        )
        setattr(credential, field, value)
        uow.session.add(credential)
        with pytest.raises(IntegrityError, match=constraint):
            await uow.commit()

    async def test_deleting_a_user_deletes_their_settings_and_credentials(
        self, uow: UnitOfWork, user: User
    ) -> None:
        await uow.owner_settings.create_defaults(user.id)
        await uow.credentials.upsert(
            user_id=user.id,
            provider=ProviderName.OPENAI,
            ciphertext=b"x",
            key_version=1,
            masked_value="••••x",
        )
        await uow.commit()

        await uow.session.execute(sqlalchemy.delete(User).where(User.id == user.id))
        await uow.commit()

        for model in (OwnerSettings, ProviderCredential):
            count = await uow.session.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(model)
            )
            assert count == 0


async def test_settings_and_credentials_need_a_real_user(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    async with UnitOfWork(session_factory) as unit:
        with pytest.raises(IntegrityError):
            await unit.owner_settings.create_defaults(uuid.uuid4())
            await unit.commit()
