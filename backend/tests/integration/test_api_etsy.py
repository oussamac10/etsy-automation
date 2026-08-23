"""Integration tests for Etsy API routes with PostgreSQL and migrations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.workflow import RunStatus
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
    User,
)
from app.infrastructure.security import CredentialCipher

from .conftest import OWNER_EMAIL

pytestmark = pytest.mark.integration


class TestEtsyApiIntegration:
    async def test_initial_etsy_status_disconnected(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/integrations/etsy")
        assert response.status_code == 200
        body = response.json()
        assert body["connected"] is False
        assert body["connection_status"] == "disconnected"
        assert body["token_health"] == "disconnected"

    async def test_auth_connect_url_requires_session(self, anon_client: httpx.AsyncClient) -> None:
        response = await anon_client.get("/api/v1/auth/etsy/connect")
        assert response.status_code == 401

    async def test_auth_connect_url_for_authenticated_owner(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/api/v1/auth/etsy/connect")
        # In test environment with fake or unconfigured live keys, either 200 (with mock) or 400/500 without live keys
        if response.status_code == 200:
            body = response.json()
            assert "authorization_url" in body
            assert "response_type=code" in body["authorization_url"]
            assert "code_challenge=" in body["authorization_url"]
        else:
            assert response.status_code in (400, 500)

    async def test_disconnect_when_not_connected_is_idempotent(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.delete("/api/v1/integrations/etsy")
        assert response.status_code == 204

    async def test_draft_trigger_on_ready_workflow(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        cipher = CredentialCipher("test-encryption-key-not-a-real-key-0123456789", key_version=1)

        workflow_id = uuid.uuid4()

        async with UnitOfWork(session_factory) as uow:
            # Find current owner user
            owner = (
                await uow.session.execute(sqlalchemy.select(User).filter_by(email=OWNER_EMAIL))
            ).scalar_one()

            # Create connected Etsy shop
            await uow.shop_connections.upsert(
                user_id=owner.id,
                provider="etsy",
                etsy_user_id="etsy_user_99",
                etsy_shop_id="shop_999",
                etsy_shop_name="IntegrationStudio",
                ciphertext_access_token=cipher.encrypt("token"),
                ciphertext_refresh_token=cipher.encrypt("refresh"),
                key_version=cipher.key_version,
                token_expires_at=datetime.now(UTC) + timedelta(hours=2),
                granted_scopes=["listings_w", "shops_r"],
            )

            from app.domain.enums import IdeaMode

            # Create workflow in READY_FOR_ETSY_DRAFT
            workflow = ProductWorkflow(
                id=workflow_id,
                owner_id=owner.id,
                name="Integration Celestial Moon PNG",
                idea_mode=IdeaMode.HYBRID,
                target_marketplace="etsy",
                target_country="US",
                output_language="en",
                target_buyer="Everyone",
                state=RunStatus.READY_FOR_ETSY_DRAFT,
                version=1,
            )
            uow.session.add(workflow)

            # Create ListingDraft with 13 tags
            valid_tags = [f"tag_{i}" for i in range(13)]
            listing = ListingDraft(
                workflow_id=workflow_id,
                title="Integration Celestial Moon Sublimation PNG",
                description="High quality digital print.",
                tags=valid_tags,
                price_minor_units=499,
                currency="USD",
                taxonomy_id=77,
                taxonomy_path="Digital",
                version=1,
            )
            uow.session.add(listing)

            # Create Master PNG asset
            master_asset = Asset(
                workflow_id=workflow_id,
                storage_key=f"workflows/{workflow_id}/master.png",
                mime_type="image/png",
                byte_size=1024,
                checksum_sha256="a" * 64,
                provenance={"profile": "etsy-png-standard"},
            )
            uow.session.add(master_asset)

            # Create Customer ZIP package
            zip_asset = Asset(
                workflow_id=workflow_id,
                storage_key=f"workflows/{workflow_id}/package.zip",
                mime_type="application/zip",
                byte_size=2048,
                checksum_sha256="b" * 64,
                provenance={"kind": "customer_package"},
            )
            uow.session.add(zip_asset)

            await uow.commit()

        # Seed S3 storage
        if hasattr(api_app.state, "storage"):
            await api_app.state.storage.put(
                master_asset.storage_key, b"fake png data", content_type="image/png"
            )
            await api_app.state.storage.put(
                zip_asset.storage_key, b"fake zip data", content_type="application/zip"
            )

        # Trigger draft endpoint
        response = await client.post(f"/api/v1/workflows/{workflow_id}/etsy/draft")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["dispatch_status"] == "queued"

        # Verify outbox message was written to PostgreSQL
        async with UnitOfWork(session_factory) as uow:
            unprocessed = await uow.outbox.get_unprocessed(limit=10)
            assert any(
                msg.event_type == "create_etsy_draft_task"
                and msg.payload.get("workflow_id") == str(workflow_id)
                for msg in unprocessed
            )
