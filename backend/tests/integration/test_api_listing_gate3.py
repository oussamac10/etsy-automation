"""Integration tests for Phase 8: Listing SEO, Trademark Screening & Gate 3 Review."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ConceptOrigin, ConceptStatus, IdeaMode
from app.domain.workflow import RiskLevel, RunStatus
from app.infrastructure.models import Asset, ListingDraft, ProductConcept

pytestmark = pytest.mark.integration


def _workflow_payload() -> dict[str, object]:
    return {
        "idea_mode": IdeaMode.MARKET_LED.value,
        "name": "Cottagecore Mushroom PNG",
        "target_country": "US",
        "output_language": "en",
        "intended_product_uses": ["tshirt", "mug"],
    }


async def _create_workflow(client: httpx.AsyncClient) -> uuid.UUID:
    response = await client.post("/api/v1/workflows", json=_workflow_payload())
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _seed_workflow_production(
    session_factory: async_sessionmaker[AsyncSession],
    workflow_id: uuid.UUID,
    *,
    api_app: Any = None,
    risk_level: RiskLevel = RiskLevel.LOW,
) -> None:
    """Seed workflow in PRODUCTION / LISTING_REVIEW with concept and master PNG."""
    async with UnitOfWork(session_factory) as uow:
        workflow = await uow.workflows.get(workflow_id)
        assert workflow is not None
        workflow.state = RunStatus.LISTING_REVIEW

        concept = ProductConcept(
            workflow_id=workflow_id,
            title="Vintage Cottagecore Mushroom",
            description="Hand-drawn botanical mushroom illustration.",
            origin=ConceptOrigin.MARKET,
            differentiation="Vintage distressed ink",
            status=ConceptStatus.APPROVED,
            risk_level=risk_level,
        )
        await uow.concepts.add(concept)
        await uow.concepts.add_prompt_version(
            concept,
            positive_prompt="vintage botanical mushroom, cottagecore aesthetic",
            negative_prompt="blurry, low quality",
            change_note="Stay Wild Mushroom Child",
        )

        # Master PNG asset (4500x5400)
        master_png = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c6360000002000100ffff03000006"
            "000557bfabd40000000049454e44ae426082"
        )
        storage_key = f"workflows/{workflow_id}/master/master.png"

        # Add asset record
        asset = Asset(
            workflow_id=workflow_id,
            storage_key=storage_key,
            mime_type="image/png",
            byte_size=len(master_png),
            checksum_sha256="a" * 64,
            width=4500,
            height=5400,
            has_alpha=True,
            has_transparent_pixels=True,
            provenance={"kind": "master_png"},
        )
        await uow.assets.add(asset)

        if api_app is not None and hasattr(api_app.state, "storage"):
            await api_app.state.storage.put(storage_key, master_png, content_type="image/png")

        # Initial listing draft
        valid_tags = [
            "png digital download",
            "sublimation design",
            "tshirt graphic",
            "transparent png",
            "printable art",
            "clipart graphic",
            "instant download",
            "tshirt design png",
            "commercial use png",
            "pod graphics",
            "mug design download",
            "sticker png",
            "digital craft file",
        ]
        draft = ListingDraft(
            workflow_id=workflow_id,
            title="Vintage Mushroom PNG Digital Download Sublimation Design",
            description="High resolution 4500x5400 px digital PNG file for t-shirts and crafts.",
            tags=valid_tags,
            ip_risk_level=risk_level,
            ip_findings={"risk_level": risk_level.value, "matches": []},
            version=1,
        )
        await uow.listing_drafts.add(draft)
        await uow.commit()


class TestListingGate3Api:
    async def test_get_listing_draft_initializes_and_returns_draft(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        workflow_id = await _create_workflow(client)

        response = await client.get(f"/api/v1/workflows/{workflow_id}/listing")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["workflow_id"] == str(workflow_id)
        assert len(data["tags"]) == 13
        assert data["version"] >= 1

    async def test_update_listing_draft_fields(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await _create_workflow(client)
        await _seed_workflow_production(session_factory, workflow_id, api_app=api_app)

        update_payload = {
            "title": "Updated Botanical Mushroom PNG Sublimation Design",
            "description": "Updated description with keywords and print details.",
            "tags": [
                "botanical png",
                "mushroom art",
                "cottagecore tee",
                "sublimation art",
                "dtg printable",
                "retro mushroom",
                "nature clipart",
                "digital download",
                "craft supply",
                "tshirt graphic",
                "aesthetic art",
                "vintage print",
                "commercial use",
            ],
            "price_minor_units": 599,
            "currency": "USD",
            "quantity": 500,
            "sku": "SKU-MUSHROOM-V2",
            "expected_version": 1,
        }

        response = await client.put(f"/api/v1/workflows/{workflow_id}/listing", json=update_payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == update_payload["title"]
        assert data["price_minor_units"] == 599
        assert data["version"] == 2

    async def test_update_listing_draft_rejects_invalid_tags_count(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await _create_workflow(client)
        await _seed_workflow_production(session_factory, workflow_id, api_app=api_app)

        update_payload = {
            "title": "Valid Listing Title Here",
            "description": "Valid listing description here.",
            "tags": ["too", "few", "tags"],
            "expected_version": 1,
        }

        response = await client.put(f"/api/v1/workflows/{workflow_id}/listing", json=update_payload)
        assert response.status_code in (400, 422)

    async def test_generate_seo_endpoint(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await _create_workflow(client)
        await _seed_workflow_production(session_factory, workflow_id, api_app=api_app)

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/listing/generate-seo?target=all"
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data["title"]) > 0
        assert len(data["tags"]) == 13

    async def test_gate3_approval_cleared_risk_succeeds(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await _create_workflow(client)
        await _seed_workflow_production(
            session_factory, workflow_id, api_app=api_app, risk_level=RiskLevel.LOW
        )

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/gates/listing",
            json={"decision": "approved", "acknowledged": False},
        )
        assert response.status_code == 200, response.text

        # Verify workflow moved to READY_FOR_ETSY_DRAFT
        wf_resp = await client.get(f"/api/v1/workflows/{workflow_id}")
        assert wf_resp.json()["state"] == "READY_FOR_ETSY_DRAFT"

    async def test_gate3_approval_warning_requires_acknowledgement(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await _create_workflow(client)
        await _seed_workflow_production(
            session_factory, workflow_id, api_app=api_app, risk_level=RiskLevel.MEDIUM
        )

        # 1. Unacknowledged fails
        fail_resp = await client.post(
            f"/api/v1/workflows/{workflow_id}/gates/listing",
            json={"decision": "approved", "acknowledged": False},
        )
        assert fail_resp.status_code == 400
        msg = (fail_resp.json().get("detail") or fail_resp.json().get("title") or "").lower()
        assert "acknowledgement" in msg or "risk" in msg

        # 2. Acknowledged succeeds
        ok_resp = await client.post(
            f"/api/v1/workflows/{workflow_id}/gates/listing",
            json={"decision": "approved", "acknowledged": True},
        )
        assert ok_resp.status_code == 200, ok_resp.text

        wf_resp = await client.get(f"/api/v1/workflows/{workflow_id}")
        assert wf_resp.json()["state"] == "READY_FOR_ETSY_DRAFT"

    async def test_gate3_approval_high_risk_strictly_blocked(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await _create_workflow(client)
        await _seed_workflow_production(
            session_factory, workflow_id, api_app=api_app, risk_level=RiskLevel.HIGH
        )

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/gates/listing",
            json={"decision": "approved", "acknowledged": True},
        )
        assert response.status_code == 400
        msg = (response.json().get("detail") or response.json().get("title") or "").lower()
        assert "high_risk" in msg or "blocked" in msg or "risk" in msg

    async def test_gate3_rejection_returns_to_production(
        self,
        client: httpx.AsyncClient,
        api_app: Any,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        workflow_id = await _create_workflow(client)
        await _seed_workflow_production(
            session_factory, workflow_id, api_app=api_app, risk_level=RiskLevel.LOW
        )

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/gates/listing",
            json={"decision": "rejected", "acknowledged": False},
        )
        assert response.status_code == 200, response.text

        wf_resp = await client.get(f"/api/v1/workflows/{workflow_id}")
        assert wf_resp.json()["state"] == "ARTWORK_APPROVED"
