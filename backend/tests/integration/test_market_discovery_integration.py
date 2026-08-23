"""Integration test for Market Opportunity Discovery background worker and endpoints."""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from worker.tasks import _run_research_async

from app.application.unit_of_work import UnitOfWork
from app.domain.workflow import RunStatus

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_market_opportunity_discovery_pipeline_and_endpoints(
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
) -> None:
    # 1. Create a Market-Led Workflow via API
    res_create = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Trend Discovery",
            "target_country": "US",
            "output_language": "en",
            "idea_mode": "market-led",
            "intended_product_uses": ["mug", "tshirt", "sticker"],
        },
    )
    assert res_create.status_code == 201
    workflow_id = uuid.UUID(res_create.json()["id"])

    # 2. Queue Research Run
    res_research = await client.post(f"/api/v1/workflows/{workflow_id}/research")
    assert res_research.status_code == 202
    run_id = uuid.UUID(res_research.json()["id"])

    # 3. Run the research background worker task
    await _run_research_async(workflow_id, run_id)

    # 4. Verify workflow state transitioned to IDEA_REVIEW and 3 opportunities created
    async with UnitOfWork(session_factory) as uow:
        db_wf = await uow.workflows.get(workflow_id)
        assert db_wf is not None
        assert db_wf.state == RunStatus.IDEA_REVIEW

        concepts = await uow.concepts.list_for_workflow(workflow_id)
        assert len(concepts) == 3

        for c in concepts:
            assert c.score_breakdown is not None
            assert "overall_score" in c.score_breakdown
            assert "opportunity_type" in c.score_breakdown
            assert "competition" in c.score_breakdown
            assert "trend_direction" in c.score_breakdown
            assert "market_validation" in c.score_breakdown
            assert "timing_label" in c.score_breakdown
            assert "why_it_could_sell" in c.score_breakdown
            assert "recommended_products" in c.score_breakdown

            prompts = await uow.concepts.prompts(c.id)
            assert len(prompts) >= 1
            assert "transparent background" in prompts[0].positive_prompt.lower()

        evidence = await uow.research.get_evidence_for_run(run_id)
        assert len(evidence) >= 3

        clusters = await uow.research.get_keyword_clusters_for_run(run_id)
        assert len(clusters) >= 3

    # 5. Test API Endpoints via HTTP client
    # GET Research Summary
    summary_resp = await client.get(f"/api/v1/workflows/{workflow_id}/research/summary")
    assert summary_resp.status_code == 200
    summary_data = summary_resp.json()
    assert len(summary_data["evidence"]) >= 3
    assert len(summary_data["keyword_clusters"]) >= 3

    # GET Concepts list
    concepts_resp = await client.get(f"/api/v1/workflows/{workflow_id}/concepts")
    assert concepts_resp.status_code == 200
    concept_list = concepts_resp.json()
    assert len(concept_list) == 3
    concept_to_refresh = concept_list[0]

    # POST Refresh single concept
    refresh_resp = await client.post(
        f"/api/v1/workflows/{workflow_id}/concepts/{concept_to_refresh['id']}/refresh"
    )
    assert refresh_resp.status_code == 200
    refreshed_concept = refresh_resp.json()
    assert refreshed_concept["id"] == concept_to_refresh["id"]
    assert "score_breakdown" in refreshed_concept
    assert "overall_score" in refreshed_concept["score_breakdown"]
