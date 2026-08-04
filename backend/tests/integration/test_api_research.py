"""Research and concept endpoints against a real database."""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ConceptOrigin, ConceptStatus, IdeaMode
from app.domain.workflow import JobStatus, RunStatus
from app.infrastructure.models import ProductConcept

pytestmark = pytest.mark.integration


def _workflow_payload(mode: IdeaMode = IdeaMode.USER_IDEA) -> dict[str, object]:
    return {
        "idea_mode": mode.value,
        "name": "Sunflower design",
        "target_country": "US",
        "output_language": "en",
        "intended_product_uses": ["mug"],
    }


class TestResearchEndpoints:
    async def test_enqueue_research_happy_path(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        # Create a workflow
        res_create = await client.post("/api/v1/workflows", json=_workflow_payload())
        assert res_create.status_code == 201
        workflow_id = res_create.json()["id"]

        # POST /research
        res_research = await client.post(f"/api/v1/workflows/{workflow_id}/research")
        assert res_research.status_code == 202
        body = res_research.json()
        assert body["workflow_id"] == workflow_id
        assert body["status"] == JobStatus.QUEUED.value

        # Verify DB states in a transaction
        async with UnitOfWork(session_factory) as uow:
            wf = await uow.workflows.get(uuid.UUID(workflow_id))
            assert wf is not None
            assert wf.state == RunStatus.RESEARCH_QUEUED

            run = await uow.research.get_latest_run(uuid.UUID(workflow_id))
            assert run is not None
            assert run.status == JobStatus.QUEUED

            # Outbox message is created
            outbox_msgs = await uow.outbox.get_unprocessed()
            assert len(outbox_msgs) == 1
            assert outbox_msgs[0].event_type == "run_research_task"

    async def test_research_endpoints_enforce_owner_isolation(
        self,
        client: httpx.AsyncClient,
        other_client: httpx.AsyncClient,
    ) -> None:
        # Create workflow as owner
        res_create = await client.post("/api/v1/workflows", json=_workflow_payload())
        workflow_id = res_create.json()["id"]

        # Other client tries to POST /research -> 404
        res_other_post = await other_client.post(f"/api/v1/workflows/{workflow_id}/research")
        assert res_other_post.status_code == 404

        # Other client tries to GET /research -> 404
        res_other_get = await other_client.get(f"/api/v1/workflows/{workflow_id}/research")
        assert res_other_get.status_code == 404

    async def test_list_research_runs(
        self, client: httpx.AsyncClient
    ) -> None:
        res_create = await client.post("/api/v1/workflows", json=_workflow_payload())
        workflow_id = res_create.json()["id"]

        # Before trigger, research list is empty
        res_get_empty = await client.get(f"/api/v1/workflows/{workflow_id}/research")
        assert res_get_empty.status_code == 200
        assert res_get_empty.json() == []

        # Trigger research
        await client.post(f"/api/v1/workflows/{workflow_id}/research")

        # Now research list has 1 item
        res_get = await client.get(f"/api/v1/workflows/{workflow_id}/research")
        assert res_get.status_code == 200
        body = res_get.json()
        assert len(body) == 1
        assert body[0]["status"] == JobStatus.QUEUED.value


class TestConceptEndpoints:
    async def test_list_concepts_empty_initially(
        self, client: httpx.AsyncClient
    ) -> None:
        res_create = await client.post("/api/v1/workflows", json=_workflow_payload())
        workflow_id = res_create.json()["id"]

        res_concepts = await client.get(f"/api/v1/workflows/{workflow_id}/concepts")
        assert res_concepts.status_code == 200
        assert res_concepts.json() == []

    async def test_revise_concept_happy_path(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        # Create workflow
        res_create = await client.post("/api/v1/workflows", json=_workflow_payload())
        workflow_id = uuid.UUID(res_create.json()["id"])

        # Inject a concept directly in DB for testing revision
        async with UnitOfWork(session_factory) as uow:
            concept = ProductConcept(
                workflow_id=workflow_id,
                title="Rustic Sunflower Tumbler",
                description="Vintage hand-painted style sunflower tumblers.",
                origin=ConceptOrigin.MARKET,
                differentiation="Textured oil paint details",
                status=ConceptStatus.PROPOSED,
            )
            await uow.concepts.add(concept)
            await uow.concepts.add_prompt_version(
                concept,
                positive_prompt="rustic sunflower",
                negative_prompt="bad quality",
                change_note="Initial prompt.",
            )
            await uow.commit()
            concept_id = concept.id

        # POST /revise
        revision_payload = {
            "positive_prompt": "updated rustic sunflower with high detail",
            "negative_prompt": "bad quality, blurry",
            "typography_instructions": "Groovy vintage font",
            "exact_slogan": "SUNFLOWER VIBES",
            "change_note": "A manual tweak to emphasize colors",
        }
        res_revise = await client.post(
            f"/api/v1/workflows/{workflow_id}/concepts/{concept_id}/revise",
            json=revision_payload,
        )
        assert res_revise.status_code == 201
        body = res_revise.json()
        assert body["concept_id"] == str(concept_id)
        assert body["version"] == 2
        assert body["positive_prompt"] == "updated rustic sunflower with high detail"
        assert body["typography_instructions"] == "Groovy vintage font"
        assert body["exact_slogan"] == "SUNFLOWER VIBES"
        assert body["change_note"] == "A manual tweak to emphasize colors"

        # Verify list concepts returns updated versions
        res_concepts = await client.get(f"/api/v1/workflows/{workflow_id}/concepts")
        assert res_concepts.status_code == 200
        concepts_list = res_concepts.json()
        assert len(concepts_list) == 1
        assert len(concepts_list[0]["prompts"]) == 2
        assert concepts_list[0]["prompts"][1]["version"] == 2

    async def test_revise_concept_enforces_owner_isolation(
        self,
        client: httpx.AsyncClient,
        other_client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        res_create = await client.post("/api/v1/workflows", json=_workflow_payload())
        workflow_id = uuid.UUID(res_create.json()["id"])

        async with UnitOfWork(session_factory) as uow:
            concept = ProductConcept(
                workflow_id=workflow_id,
                title="Rustic Sunflower Tumbler",
                description="Vintage hand-painted style sunflower tumblers.",
                origin=ConceptOrigin.MARKET,
                differentiation="Textured oil paint details",
                status=ConceptStatus.PROPOSED,
            )
            await uow.concepts.add(concept)
            await uow.concepts.add_prompt_version(
                concept,
                positive_prompt="rustic sunflower",
                negative_prompt="bad quality",
                change_note="Initial prompt.",
            )
            await uow.commit()
            concept_id = concept.id

        revision_payload = {
            "positive_prompt": "updated positive prompt",
            "negative_prompt": "no background",
            "change_note": "Unauthorised access attempt",
        }
        # Other client tries to revise -> 404
        res_other = await other_client.post(
            f"/api/v1/workflows/{workflow_id}/concepts/{concept_id}/revise",
            json=revision_payload,
        )
        assert res_other.status_code == 404
