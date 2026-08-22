"""Regression and integration tests for listing generation context staleness and isolation."""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ConceptOrigin, ConceptStatus, IdeaMode, Seasonality
from app.domain.workflow import RiskLevel
from app.infrastructure.models import ProductConcept

pytestmark = pytest.mark.integration


def _workflow_payload(name: str = "US Trend Discovery") -> dict[str, object]:
    return {
        "idea_mode": IdeaMode.MARKET_LED.value,
        "name": name,
        "target_country": "US",
        "output_language": "en",
        "intended_product_uses": ["tshirt", "mug", "sticker"],
    }


async def _create_workflow(
    client: httpx.AsyncClient, name: str = "US Trend Discovery"
) -> uuid.UUID:
    response = await client.post("/api/v1/workflows", json=_workflow_payload(name=name))
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _seed_concept_with_prompt(
    session_factory: async_sessionmaker[AsyncSession],
    workflow_id: uuid.UUID,
    *,
    title: str,
    status: ConceptStatus = ConceptStatus.PROPOSED,
    description: str = "Detailed description of concept",
    positive_prompt: str = "Positive prompt description",
) -> uuid.UUID:
    async with UnitOfWork(session_factory) as uow:
        concept = ProductConcept(
            workflow_id=workflow_id,
            title=title,
            description=description,
            origin=ConceptOrigin.MARKET,
            differentiation="Unique style",
            status=status,
            risk_level=RiskLevel.LOW,
            target_buyer="Teachers & Crafters",
            seasonality=Seasonality.SEASONAL,
            score_breakdown={"primary_keywords": [f"{title.lower()} png", "sublimation design"]},
        )
        await uow.concepts.add(concept)
        await uow.concepts.add_prompt_version(
            concept,
            positive_prompt=positive_prompt,
            negative_prompt="blurry, watermark",
            change_note="Seeded prompt",
        )
        await uow.commit()
        return concept.id


async def test_listing_generation_uses_active_approved_concept_not_first_concept(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Listing generation must use active APPROVED concept, not 1st unapproved concept."""
    wf_id = await _create_workflow(client, name="Trend Workflow")

    # 1. Seed Concept 1: Sarcastic Bookworm Skeleton (Unapproved / Proposed)
    await _seed_concept_with_prompt(
        session_factory,
        wf_id,
        title="Sarcastic Bookworm Skeleton Iced Coffee Lover",
        status=ConceptStatus.PROPOSED,
        description="Relaxed skeleton reading a book with iced coffee illustration in cozy sweater",
        positive_prompt="Vintage skeleton with reading glasses, books, and iced coffee cup",
    )

    # 2. Seed Concept 2: Highland Cow Teacher Back to School Calf (APPROVED)
    c2_id = await _seed_concept_with_prompt(
        session_factory,
        wf_id,
        title="Highland Cow Teacher Back to School Calf",
        status=ConceptStatus.APPROVED,
        description="Cute highland cow calf wearing teacher glasses and holding apples and pencils",
        positive_prompt="Cute fluffy highland cow calf with big glasses, pencil, back to school",
    )

    # 3. Generate SEO Listing Copy
    res = await client.post(f"/api/v1/workflows/{wf_id}/listing/generate-seo?target=all")
    assert res.status_code == 200, res.text
    data = res.json()

    # 4. Assert listing copy matches Concept 2 and NOT Concept 1
    title_lower = data["title"].lower()
    description_lower = data["description"].lower()
    summary_lower = (data.get("shopping_cart_summary") or "").lower()

    # Must contain Highland Cow / Teacher / Cow signals
    assert "highland" in title_lower or "cow" in title_lower or "teacher" in title_lower

    # Must NEVER contain Skeleton / Bookworm signals
    assert "skeleton" not in title_lower
    assert "bookworm" not in title_lower
    assert "skeleton" not in description_lower
    assert "skeleton" not in summary_lower

    # Provenance assertions
    assert data["concept_id"] == str(c2_id)
    assert data["listing_context_hash"] is not None
    assert data["is_stale"] is False


async def test_cross_campaign_isolation(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test two distinct campaigns: Campaign A (Skeleton) and Campaign B (Highland Cow)."""
    # Campaign A
    wf_a = await _create_workflow(client, name="Skeleton Campaign")
    ca_id = await _seed_concept_with_prompt(
        session_factory,
        wf_a,
        title="Sarcastic Bookworm Skeleton Iced Coffee",
        status=ConceptStatus.APPROVED,
        description="Bookworm skeleton reading books with iced coffee",
        positive_prompt="Skeleton reader design",
    )

    # Campaign B
    wf_b = await _create_workflow(client, name="Highland Cow Campaign")
    cb_id = await _seed_concept_with_prompt(
        session_factory,
        wf_b,
        title="Highland Cow Teacher Back to School Calf",
        status=ConceptStatus.APPROVED,
        description="Highland cow teacher back to school",
        positive_prompt="Highland cow calf teacher",
    )

    # Generate A
    res_a = await client.post(f"/api/v1/workflows/{wf_a}/listing/generate-seo?target=all")
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert "skeleton" in data_a["title"].lower() or "bookworm" in data_a["title"].lower()
    assert "highland" not in data_a["title"].lower()
    assert data_a["concept_id"] == str(ca_id)

    # Generate B
    res_b = await client.post(f"/api/v1/workflows/{wf_b}/listing/generate-seo?target=all")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert "highland" in data_b["title"].lower() or "cow" in data_b["title"].lower()
    assert "skeleton" not in data_b["title"].lower()
    assert data_b["concept_id"] == str(cb_id)


async def test_staleness_detected_when_concept_switches(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """When active concept switches after listing generation, draft must be reported as stale."""
    wf_id = await _create_workflow(client, name="Multi Concept Switch Workflow")

    c1_id = await _seed_concept_with_prompt(
        session_factory,
        wf_id,
        title="Highland Cow Teacher Back to School Calf",
        status=ConceptStatus.APPROVED,
    )

    # Generate listing for Concept 1
    res1 = await client.post(f"/api/v1/workflows/{wf_id}/listing/generate-seo?target=all")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_stale"] is False
    assert data1["concept_id"] == str(c1_id)

    # Now switch active approved concept to Concept 2
    async with UnitOfWork(session_factory) as uow:
        # Mark concept 1 as archived/proposed
        c1 = await uow.concepts.get(c1_id)
        assert c1 is not None
        c1.status = ConceptStatus.PROPOSED

        # Create and approve concept 2
        c2 = ProductConcept(
            workflow_id=wf_id,
            title="Retro Ghost Halloween Sublimation Design",
            description="Cute retro ghost holding pumpkin coffee cup",
            differentiation="Unique retro ghost style",
            origin=ConceptOrigin.MARKET,
            status=ConceptStatus.APPROVED,
            risk_level=RiskLevel.LOW,
        )
        await uow.concepts.add(c2)
        await uow.commit()

    # Query listing draft -> must now report is_stale: True
    res_get = await client.get(f"/api/v1/workflows/{wf_id}/listing")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["is_stale"] is True
    assert data_get["stale_reason"] is not None
