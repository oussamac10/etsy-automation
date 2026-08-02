"""Owner settings and provider credentials end to end.

The credential tests exist mainly to prove two negatives: no plaintext secret
appears in an API response, and none exists in the database.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction, ProviderName
from app.infrastructure.models import OwnerSettings, ProviderCredential
from app.infrastructure.security import CredentialCipher

from .conftest import OWNER_EMAIL, open_client

pytestmark = pytest.mark.integration

SECRET = "sk-test-not-a-real-provider-key-abcd1234"


class TestSettingsDefaults:
    async def test_first_read_materialises_defaults(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/settings")
        assert response.status_code == 200
        body = response.json()
        assert body["target_marketplace"] == "etsy"
        assert body["target_country"] == "US"
        assert body["currency"] == "USD"
        assert body["default_language"] == "en"
        assert body["default_quality_tier"] == "draft"
        assert body["require_transparent_background"] is True
        assert Decimal(body["daily_budget"]) == Decimal("2.00")
        assert Decimal(body["monthly_budget"]) == Decimal("30.00")

    async def test_reading_twice_creates_one_row(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await client.get("/api/v1/settings")
        await client.get("/api/v1/settings")
        async with UnitOfWork(session_factory) as uow:
            count = await uow.session.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(OwnerSettings)
            )
        assert count == 1

    async def test_settings_require_a_session(self, anon_client: httpx.AsyncClient) -> None:
        assert (await anon_client.get("/api/v1/settings")).status_code == 401
        assert (await anon_client.patch("/api/v1/settings", json={})).status_code == 401


class TestSettingsUpdate:
    async def test_a_partial_update_leaves_everything_else_alone(
        self, client: httpx.AsyncClient
    ) -> None:
        before = (await client.get("/api/v1/settings")).json()
        response = await client.patch("/api/v1/settings", json={"target_country": "gb"})
        assert response.status_code == 200
        after = response.json()

        assert after["target_country"] == "GB"
        unchanged = {k: v for k, v in after.items() if k not in {"target_country", "updated_at"}}
        assert unchanged == {
            k: v for k, v in before.items() if k not in {"target_country", "updated_at"}
        }

    async def test_an_empty_update_is_not_an_error(self, client: httpx.AsyncClient) -> None:
        assert (await client.patch("/api/v1/settings", json={})).status_code == 200

    async def test_budgets_round_trip_exactly(self, client: httpx.AsyncClient) -> None:
        """Two decimal places in, two decimal places out. No float drift."""
        response = await client.patch(
            "/api/v1/settings",
            json={"daily_budget": "1.07", "monthly_budget": "19.99"},
        )
        body = response.json()
        assert Decimal(body["daily_budget"]) == Decimal("1.07")
        assert Decimal(body["monthly_budget"]) == Decimal("19.99")

        again = (await client.get("/api/v1/settings")).json()
        assert Decimal(again["daily_budget"]) == Decimal("1.07")

    async def test_budgets_are_stored_as_minor_units(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await client.patch("/api/v1/settings", json={"daily_budget": "1.07"})
        async with UnitOfWork(session_factory) as uow:
            row = (await uow.session.execute(sqlalchemy.select(OwnerSettings))).scalar_one()
            assert row.daily_budget_minor == 107

    async def test_a_daily_budget_above_the_monthly_one_is_rejected(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.patch("/api/v1/settings", json={"daily_budget": "500.00"})
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid-budget-relation")

    async def test_lists_and_notes_persist(self, client: httpx.AsyncClient) -> None:
        response = await client.patch(
            "/api/v1/settings",
            json={
                "style_preferences": ["hand drawn", "muted palette"],
                "avoid_terms": ["celebrity likeness"],
                "style_notes": "No neon.",
                "default_quality_tier": "final",
                "min_output_pixels": 4000,
            },
        )
        body = response.json()
        assert body["style_preferences"] == ["hand drawn", "muted palette"]
        assert body["avoid_terms"] == ["celebrity likeness"]
        assert body["default_quality_tier"] == "final"
        assert body["min_output_pixels"] == 4000

    @pytest.mark.parametrize(
        "payload",
        [
            {"currency": "XYZ"},
            {"target_marketplace": "amazon"},
            {"target_country": "USA"},
            {"daily_budget": "-1.00"},
            {"daily_budget": "1.005"},
            {"min_output_pixels": 10},
            {"weekly_research_weekday": 9},
            {"weekly_research_hour_utc": 25},
            {"unknown_setting": True},
        ],
    )
    async def test_invalid_values_are_422(
        self, client: httpx.AsyncClient, payload: dict[str, object]
    ) -> None:
        response = await client.patch("/api/v1/settings", json=payload)
        assert response.status_code == 422
        assert response.headers["content-type"].startswith("application/problem+json")

    async def test_a_settings_change_is_audited(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await client.patch("/api/v1/settings", json={"default_language": "fr"})
        async with UnitOfWork(session_factory) as uow:
            from app.infrastructure.models import AuditEvent

            rows = (
                (
                    await uow.session.execute(
                        sqlalchemy.select(AuditEvent).where(
                            AuditEvent.action == AuditAction.SETTINGS_UPDATED
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1
        assert rows[0].after == {"default_language": "fr"}


class TestSettingsIsolation:
    async def test_each_owner_has_their_own_settings(
        self, client: httpx.AsyncClient, other_client: httpx.AsyncClient
    ) -> None:
        await client.patch("/api/v1/settings", json={"target_country": "GB"})
        assert (await other_client.get("/api/v1/settings")).json()["target_country"] == "US"
        assert (await client.get("/api/v1/settings")).json()["target_country"] == "GB"


class TestCredentials:
    async def test_every_provider_is_listed_as_unconfigured(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/api/v1/settings/credentials")
        assert response.status_code == 200
        items = response.json()["items"]
        assert {item["provider"] for item in items} == {p.value for p in ProviderName}
        assert all(item["configured"] is False for item in items)
        assert all(item["masked_value"] is None for item in items)

    async def test_storing_returns_only_a_mask(self, client: httpx.AsyncClient) -> None:
        response = await client.put(
            "/api/v1/settings/credentials/openai",
            json={"secret": SECRET, "label": "main account"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["configured"] is True
        assert body["masked_value"] == "•" * 8 + SECRET[-4:]
        assert body["label"] == "main account"
        assert SECRET not in response.text

    async def test_the_secret_is_never_readable_through_the_api(
        self, client: httpx.AsyncClient
    ) -> None:
        await client.put("/api/v1/settings/credentials/openai", json={"secret": SECRET})
        listed = await client.get("/api/v1/settings/credentials")
        assert SECRET not in listed.text
        # And there is no endpoint that would return it.
        assert (await client.get("/api/v1/settings/credentials/openai")).status_code == 405

    async def test_the_database_holds_ciphertext_only(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        settings: object,
    ) -> None:
        await client.put("/api/v1/settings/credentials/openai", json={"secret": SECRET})

        async with UnitOfWork(session_factory) as uow:
            row = (await uow.session.execute(sqlalchemy.select(ProviderCredential))).scalar_one()
            assert SECRET.encode() not in row.ciphertext
            assert SECRET not in repr(row.__dict__)
            assert row.key_version == 1

            # Round-trips with the configured key, which is the point of storing it.
            cipher = CredentialCipher(
                settings.encryption_key.get_secret_value(),  # type: ignore[attr-defined]
                key_version=settings.encryption_key_version,  # type: ignore[attr-defined]
            )
            assert cipher.decrypt(row.ciphertext, key_version=row.key_version) == SECRET

    async def test_replacing_overwrites_in_place(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """One row per provider: a stale secret must not linger beside the new one."""
        await client.put("/api/v1/settings/credentials/openai", json={"secret": SECRET})
        replacement = "sk-test-replacement-value-wxyz9876"
        response = await client.put(
            "/api/v1/settings/credentials/openai", json={"secret": replacement}
        )
        assert response.json()["masked_value"] == "•" * 8 + "9876"

        async with UnitOfWork(session_factory) as uow:
            rows = (
                (await uow.session.execute(sqlalchemy.select(ProviderCredential))).scalars().all()
            )
        assert len(rows) == 1

    async def test_deleting_removes_it(self, client: httpx.AsyncClient) -> None:
        await client.put("/api/v1/settings/credentials/openai", json={"secret": SECRET})
        assert (await client.delete("/api/v1/settings/credentials/openai")).status_code == 204

        items = (await client.get("/api/v1/settings/credentials")).json()["items"]
        openai = next(item for item in items if item["provider"] == "openai")
        assert openai["configured"] is False

    async def test_deleting_what_is_not_there_is_a_404(self, client: httpx.AsyncClient) -> None:
        response = await client.delete("/api/v1/settings/credentials/recraft")
        assert response.status_code == 404

    async def test_an_unknown_provider_is_rejected(self, client: httpx.AsyncClient) -> None:
        response = await client.put(
            "/api/v1/settings/credentials/not-a-provider", json={"secret": SECRET}
        )
        assert response.status_code == 422

    async def test_a_too_short_secret_is_rejected(self, client: httpx.AsyncClient) -> None:
        assert (
            await client.put("/api/v1/settings/credentials/openai", json={"secret": "short"})
        ).status_code == 422

    async def test_credentials_are_owner_scoped(
        self, client: httpx.AsyncClient, other_client: httpx.AsyncClient
    ) -> None:
        await client.put("/api/v1/settings/credentials/openai", json={"secret": SECRET})

        items = (await other_client.get("/api/v1/settings/credentials")).json()["items"]
        assert all(item["configured"] is False for item in items)
        # And the other owner cannot delete it.
        assert (await other_client.delete("/api/v1/settings/credentials/openai")).status_code == 404

    async def test_storing_is_audited_with_the_mask_only(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        await client.put("/api/v1/settings/credentials/openai", json={"secret": SECRET})
        async with UnitOfWork(session_factory) as uow:
            from app.infrastructure.models import AuditEvent

            row = (
                await uow.session.execute(
                    sqlalchemy.select(AuditEvent).where(
                        AuditEvent.action == AuditAction.CREDENTIAL_STORED
                    )
                )
            ).scalar_one()
        assert SECRET not in repr(row.after) + repr(row.summary)
        assert row.after == {"provider": "openai", "masked": "•" * 8 + SECRET[-4:]}

    async def test_deleting_is_audited(
        self,
        client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        await client.put("/api/v1/settings/credentials/openai", json={"secret": SECRET})
        await client.delete("/api/v1/settings/credentials/openai")
        async with UnitOfWork(session_factory) as uow:
            from app.infrastructure.models import AuditEvent

            count = await uow.session.scalar(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == AuditAction.CREDENTIAL_DELETED)
            )
        assert count == 1


class TestMissingEncryptionKey:
    async def test_storing_fails_safely_when_encryption_is_unavailable(
        self, api_app: object, accounts: dict[str, uuid.UUID]
    ) -> None:
        """No cipher means 503 and no row — never a plaintext fallback."""
        api_app.state.credential_cipher = None  # type: ignore[attr-defined]
        signed_in = await open_client(api_app, OWNER_EMAIL)
        try:
            response = await signed_in.put(
                "/api/v1/settings/credentials/openai", json={"secret": SECRET}
            )
            assert response.status_code == 503
            assert response.json()["type"].endswith("/encryption-unavailable")
            assert SECRET not in response.text

            items = (await signed_in.get("/api/v1/settings/credentials")).json()["items"]
            assert all(item["configured"] is False for item in items)
        finally:
            await signed_in.aclose()
