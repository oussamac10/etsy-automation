"""Authentication end to end against a real database.

Covers the login/logout/current-user contract, the session lifecycle, CSRF and
the two things that must never happen: a password reaching a response, and a
disabled account authenticating.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.infrastructure.models import User, UserSession
from app.infrastructure.security import hash_session_token

from .conftest import OTHER_EMAIL, OWNER_EMAIL, TEST_PASSWORD, open_client

pytestmark = pytest.mark.integration


class TestLogin:
    async def test_valid_credentials_open_a_session(
        self, anon_client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        response = await anon_client.post(
            "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == str(accounts["owner"])
        assert body["user"]["email"] == OWNER_EMAIL
        assert "etsy_session" in anon_client.cookies
        assert "etsy_csrf" in anon_client.cookies

    async def test_the_session_token_is_never_in_the_body(
        self, anon_client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        response = await anon_client.post(
            "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": TEST_PASSWORD}
        )
        assert "session_token" not in response.text
        assert anon_client.cookies["etsy_session"] not in response.text
        assert TEST_PASSWORD not in response.text
        assert "password" not in response.text.lower()

    async def test_the_session_cookie_is_httponly(
        self, anon_client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        response = await anon_client.post(
            "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": TEST_PASSWORD}
        )
        cookies = [h for h in response.headers.get_list("set-cookie") if "etsy_session=" in h]
        assert len(cookies) == 1
        assert "HttpOnly" in cookies[0]
        assert "SameSite=lax" in cookies[0].replace("samesite", "SameSite")
        # The CSRF cookie must be readable, which is the whole double-submit idea.
        csrf = [h for h in response.headers.get_list("set-cookie") if "etsy_csrf=" in h]
        assert "HttpOnly" not in csrf[0]

    @pytest.mark.parametrize(
        ("email", "password"),
        [
            (OWNER_EMAIL, "wrong-password-entirely"),
            ("nobody@example.invalid", TEST_PASSWORD),
            ("nobody@example.invalid", "wrong-password-entirely"),
        ],
    )
    async def test_bad_credentials_are_one_generic_401(
        self,
        anon_client: httpx.AsyncClient,
        accounts: dict[str, uuid.UUID],
        email: str,
        password: str,
    ) -> None:
        """An unknown account and a wrong password must be indistinguishable."""
        response = await anon_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["detail"] == "Invalid email or password."
        assert "etsy_session" not in anon_client.cookies

    async def test_email_is_case_insensitive(
        self, anon_client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        response = await anon_client.post(
            "/api/v1/auth/login",
            json={"email": OWNER_EMAIL.upper(), "password": TEST_PASSWORD},
        )
        assert response.status_code == 200

    async def test_a_disabled_account_cannot_sign_in(
        self,
        anon_client: httpx.AsyncClient,
        accounts: dict[str, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        async with UnitOfWork(session_factory) as uow:
            user = await uow.users.get(accounts["owner"])
            assert user is not None
            user.is_active = False
            await uow.commit()

        response = await anon_client.post(
            "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 401

    async def test_a_user_without_a_password_cannot_sign_in(
        self,
        anon_client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        clean_database: None,
    ) -> None:
        """Phase 1/2 fixtures created users with no credential. They stay locked."""
        async with UnitOfWork(session_factory) as uow:
            await uow.users.add(email="legacy@example.invalid", display_name="Legacy")
            await uow.commit()

        response = await anon_client.post(
            "/api/v1/auth/login",
            json={"email": "legacy@example.invalid", "password": TEST_PASSWORD},
        )
        assert response.status_code == 401

    async def test_a_malformed_request_is_a_422(self, anon_client: httpx.AsyncClient) -> None:
        response = await anon_client.post("/api/v1/auth/login", json={"email": "x"})
        assert response.status_code == 422


class TestCurrentUser:
    async def test_me_returns_the_signed_in_owner(
        self, client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["id"] == str(accounts["owner"])
        assert "password_hash" not in response.text

    async def test_me_requires_a_session(self, anon_client: httpx.AsyncClient) -> None:
        response = await anon_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["type"].endswith("/not-authenticated")

    async def test_a_forged_cookie_is_rejected(
        self, anon_client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        anon_client.cookies.set("etsy_session", "made-up-token", domain="testserver")
        assert (await anon_client.get("/api/v1/auth/me")).status_code == 401

    async def test_an_expired_session_is_rejected(
        self,
        anon_client: httpx.AsyncClient,
        accounts: dict[str, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Written directly: the CHECK constraint forbids expiring a live row."""
        now = datetime.now(UTC)
        async with UnitOfWork(session_factory) as uow:
            uow.session.add(
                UserSession(
                    user_id=accounts["owner"],
                    token_hash=hash_session_token("expired-token"),
                    csrf_token="csrf",
                    created_at=now - timedelta(hours=2),
                    expires_at=now - timedelta(hours=1),
                    last_seen_at=now - timedelta(hours=2),
                )
            )
            await uow.commit()

        anon_client.cookies.set("etsy_session", "expired-token", domain="testserver")
        assert (await anon_client.get("/api/v1/auth/me")).status_code == 401

    async def test_a_revoked_session_is_rejected(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        assert (await client.get("/api/v1/auth/me")).status_code == 200

        token_hash = hash_session_token(client.cookies["etsy_session"])
        async with UnitOfWork(session_factory) as uow:
            session = await uow.sessions.get_by_token_hash(token_hash)
            assert session is not None
            await uow.sessions.revoke(session, now=datetime.now(UTC))
            await uow.commit()

        assert (await client.get("/api/v1/auth/me")).status_code == 401

    async def test_the_expiry_constraint_refuses_a_backdated_expiry(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """The database, not just the code, refuses an already-expired session."""
        token_hash = hash_session_token(client.cookies["etsy_session"])
        with pytest.raises(sqlalchemy.exc.IntegrityError, match="expiry_after_creation"):
            async with UnitOfWork(session_factory) as uow:
                session = await uow.sessions.get_by_token_hash(token_hash)
                assert session is not None
                session.expires_at = datetime.now(UTC) - timedelta(days=1)
                await uow.commit()

    async def test_disabling_an_account_ends_its_sessions_immediately(
        self,
        client: httpx.AsyncClient,
        accounts: dict[str, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        async with UnitOfWork(session_factory) as uow:
            user = await uow.users.get(accounts["owner"])
            assert user is not None
            user.is_active = False
            await uow.commit()

        assert (await client.get("/api/v1/auth/me")).status_code == 401


class TestCsrf:
    async def test_a_mutation_without_the_csrf_header_is_refused(
        self, api_app: object, accounts: dict[str, uuid.UUID]
    ) -> None:
        signed_in = await open_client(api_app, OWNER_EMAIL)
        del signed_in.headers["x-csrf-token"]
        try:
            response = await signed_in.post(
                "/api/v1/workflows",
                json={
                    "idea_mode": "user-idea",
                    "name": "No CSRF token",
                    "target_country": "US",
                    "output_language": "en",
                },
            )
            assert response.status_code == 403
            assert response.json()["type"].endswith("/csrf-failed")
        finally:
            await signed_in.aclose()

    async def test_a_wrong_csrf_token_is_refused(
        self, api_app: object, accounts: dict[str, uuid.UUID]
    ) -> None:
        signed_in = await open_client(api_app, OWNER_EMAIL)
        signed_in.headers["x-csrf-token"] = "not-the-right-token"
        try:
            response = await signed_in.patch("/api/v1/settings", json={"default_language": "fr"})
            assert response.status_code == 403
        finally:
            await signed_in.aclose()

    async def test_reads_do_not_need_a_csrf_token(
        self, api_app: object, accounts: dict[str, uuid.UUID]
    ) -> None:
        signed_in = await open_client(api_app, OWNER_EMAIL)
        del signed_in.headers["x-csrf-token"]
        try:
            assert (await signed_in.get("/api/v1/auth/me")).status_code == 200
        finally:
            await signed_in.aclose()


class TestLogout:
    async def test_logout_ends_the_session(self, client: httpx.AsyncClient) -> None:
        assert (await client.post("/api/v1/auth/logout")).status_code == 204
        # The cookie is cleared and the session no longer authenticates.
        assert (await client.get("/api/v1/auth/me")).status_code == 401

    async def test_logout_is_idempotent(self, client: httpx.AsyncClient) -> None:
        assert (await client.post("/api/v1/auth/logout")).status_code == 204
        assert (await client.post("/api/v1/auth/logout")).status_code == 204

    async def test_logout_without_a_session_still_succeeds(
        self, anon_client: httpx.AsyncClient
    ) -> None:
        assert (await anon_client.post("/api/v1/auth/logout")).status_code == 204

    async def test_a_revoked_session_row_is_kept(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Revoked, not deleted: the session history stays auditable."""
        token_hash = hash_session_token(client.cookies["etsy_session"])
        await client.post("/api/v1/auth/logout")

        async with UnitOfWork(session_factory) as uow:
            session = await uow.sessions.get_by_token_hash(token_hash)
            assert session is not None
            assert session.revoked_at is not None

    async def test_logging_out_does_not_touch_another_session(
        self,
        client: httpx.AsyncClient,
        other_client: httpx.AsyncClient,
    ) -> None:
        await client.post("/api/v1/auth/logout")
        assert (await other_client.get("/api/v1/auth/me")).status_code == 200


class TestSessionStorage:
    async def test_the_token_is_stored_only_as_a_hash(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        token = client.cookies["etsy_session"]
        async with UnitOfWork(session_factory) as uow:
            rows = (await uow.session.execute(sqlalchemy.select(UserSession))).scalars().all()
            assert len(rows) == 1
            assert rows[0].token_hash == hash_session_token(token)
            assert token not in rows[0].token_hash

    async def test_the_password_is_stored_only_as_an_argon2_hash(
        self,
        accounts: dict[str, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        async with UnitOfWork(session_factory) as uow:
            rows = (await uow.session.execute(sqlalchemy.select(User))).scalars().all()
            assert rows
            for row in rows:
                assert row.password_hash is not None
                assert row.password_hash.startswith("$argon2id$")
                assert TEST_PASSWORD not in row.password_hash

    async def test_two_accounts_get_two_independent_sessions(
        self,
        client: httpx.AsyncClient,
        other_client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        assert client.cookies["etsy_session"] != other_client.cookies["etsy_session"]
        async with UnitOfWork(session_factory) as uow:
            count = await uow.session.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(UserSession)
            )
            assert count == 2


class TestAuditTrail:
    async def test_a_successful_login_is_audited(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        async with UnitOfWork(session_factory) as uow:
            actions = await _audit_actions(uow)
        assert AuditAction.LOGIN_SUCCEEDED in actions

    async def test_a_failed_login_is_audited_without_the_attempted_password(
        self,
        anon_client: httpx.AsyncClient,
        accounts: dict[str, uuid.UUID],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        await anon_client.post(
            "/api/v1/auth/login",
            json={"email": OTHER_EMAIL, "password": "a-guessed-password-value"},
        )
        async with UnitOfWork(session_factory) as uow:
            rows = await _audit_rows(uow)
        failures = [row for row in rows if row.action is AuditAction.LOGIN_FAILED]
        assert len(failures) == 1
        serialised = repr(failures[0].event_metadata) + repr(failures[0].summary)
        assert "a-guessed-password-value" not in serialised

    async def test_logout_is_audited(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        await client.post("/api/v1/auth/logout")
        async with UnitOfWork(session_factory) as uow:
            assert AuditAction.LOGOUT in await _audit_actions(uow)


class TestRegister:
    async def test_register_creates_new_user_and_sets_cookies(
        self, anon_client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        email = "new-register@example.invalid"
        response = await anon_client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "display_name": "New Owner",
                "password": "some-safe-password-12345",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == email
        assert "etsy_session" in anon_client.cookies
        assert "etsy_csrf" in anon_client.cookies

        # Verify in database
        async with UnitOfWork(session_factory) as uow:
            db_user = await uow.users.get_by_email(email)
            assert db_user is not None
            assert db_user.display_name == "New Owner"

    async def test_register_fails_if_email_exists(
        self, anon_client: httpx.AsyncClient, accounts: dict[str, uuid.UUID]
    ) -> None:
        response = await anon_client.post(
            "/api/v1/auth/register",
            json={
                "email": OWNER_EMAIL,
                "display_name": "Duplicate Owner",
                "password": "password-12345",
            },
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["title"].lower()


async def _audit_rows(uow: UnitOfWork) -> list:  # type: ignore[type-arg]
    from app.infrastructure.models import AuditEvent

    result = await uow.session.execute(sqlalchemy.select(AuditEvent))
    return list(result.scalars().all())


async def _audit_actions(uow: UnitOfWork) -> set[AuditAction]:
    return {row.action for row in await _audit_rows(uow)}
