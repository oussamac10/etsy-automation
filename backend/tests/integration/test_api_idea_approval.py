"""Gate 1: enqueueing research idempotently and approving a reviewed concept.

The rules under test are the ones that protect money and provenance: a replayed
request must not buy a second research run, and an approval must name the exact
concept version a human read.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ConceptOrigin, ConceptStatus, IdeaMode
from app.domain.workflow import ApprovalDecision, ApprovalGate, RiskLevel, RunStatus
from app.infrastructure.models import ProductConcept

pytestmark = pytest.mark.integration


def _workflow_payload(mode: IdeaMode = IdeaMode.MARKET_LED) -> dict[str, object]:
    return {
        "idea_mode": mode.value,
        "name": "Sleepy fox mugs",
        "target_country": "US",
        "output_language": "en",
        "intended_product_uses": ["mug"],
    }


async def _create_workflow(client: httpx.AsyncClient) -> uuid.UUID:
    response = await client.post("/api/v1/workflows", json=_workflow_payload())
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _seed_concept(
    session_factory: async_sessionmaker[AsyncSession],
    workflow_id: uuid.UUID,
    *,
    title: str = "Rustic Sunflower Tumbler",
    risk_level: RiskLevel = RiskLevel.LOW,
) -> uuid.UUID:
    """A concept with one prompt version, as a completed research run leaves it."""
    async with UnitOfWork(session_factory) as uow:
        concept = ProductConcept(
            workflow_id=workflow_id,
            title=title,
            description="Vintage hand-painted style sunflower tumblers.",
            origin=ConceptOrigin.MARKET,
            differentiation="Textured oil paint details",
            status=ConceptStatus.PROPOSED,
            risk_level=risk_level,
        )
        await uow.concepts.add(concept)
        await uow.concepts.add_prompt_version(
            concept,
            positive_prompt="rustic sunflower, isolated on transparent background",
            negative_prompt="background, mockup, watermark",
            change_note="Initial prompt.",
        )
        await uow.commit()
        return concept.id


async def _move_to_idea_review(
    session_factory: async_sessionmaker[AsyncSession], workflow_id: uuid.UUID
) -> None:
    """Put the workflow at gate 1 without running the paid research task."""
    async with UnitOfWork(session_factory) as uow:
        workflow = await uow.workflows.get(workflow_id)
        assert workflow is not None
        for state in (
            RunStatus.RESEARCH_QUEUED,
            RunStatus.RESEARCHING,
            RunStatus.IDEA_REVIEW,
        ):
            if workflow.state == state:
                continue
            await uow.workflows.transition(
                workflow,
                to_state=state,
                expected_version=workflow.version,
                reason="Test fixture",
                actor="test",
            )
        await uow.commit()


class TestEnqueueResearchIdempotency:
    async def test_replaying_a_key_returns_the_same_run(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        headers = {"Idempotency-Key": "run-key-1"}

        first = await client.post(f"/api/v1/workflows/{workflow_id}/research", headers=headers)
        second = await client.post(f"/api/v1/workflows/{workflow_id}/research", headers=headers)

        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["id"] == second.json()["id"]

        # One run and one queued job, not two of each.
        async with UnitOfWork(session_factory) as uow:
            runs = await uow.research.list_runs_for_workflow(workflow_id)
            assert len(runs) == 1
            assert len(await uow.outbox.get_unprocessed()) == 1

    async def test_a_key_cannot_be_reused_for_another_workflow(
        self, client: httpx.AsyncClient
    ) -> None:
        first_workflow = await _create_workflow(client)
        second_workflow = await _create_workflow(client)
        headers = {"Idempotency-Key": "run-key-2"}

        await client.post(f"/api/v1/workflows/{first_workflow}/research", headers=headers)
        reused = await client.post(f"/api/v1/workflows/{second_workflow}/research", headers=headers)

        # Returning the first workflow's run here would hand the caller another
        # workflow's data; refusing is the only honest answer.
        assert reused.status_code == 409

    async def test_a_second_request_without_a_key_is_refused_while_one_is_queued(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)

        first = await client.post(f"/api/v1/workflows/{workflow_id}/research")
        second = await client.post(f"/api/v1/workflows/{workflow_id}/research")

        assert first.status_code == 202
        # Without a key there is nothing to match on, so the state machine is
        # what stops the double spend: the workflow is already queued.
        assert second.status_code == 409

        async with UnitOfWork(session_factory) as uow:
            runs = await uow.research.list_runs_for_workflow(workflow_id)
            assert len(runs) == 1


class TestIdeaApprovalGate:
    async def test_approving_a_concept_records_the_reviewed_version(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        concept_id = await _seed_concept(session_factory, workflow_id)
        await _move_to_idea_review(session_factory, workflow_id)

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
                "target_type": "ProductConcept",
                "target_id": str(concept_id),
                "target_version": 1,
            },
        )

        assert response.status_code == 201, response.text
        assert response.json()["target_version"] == 1

        async with UnitOfWork(session_factory) as uow:
            concept = await uow.concepts.get(concept_id)
            assert concept is not None
            assert concept.status == ConceptStatus.APPROVED
            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None
            assert workflow.name == concept.title

    async def test_repeating_the_same_decision_records_one_approval(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        concept_id = await _seed_concept(session_factory, workflow_id)
        await _move_to_idea_review(session_factory, workflow_id)
        body = {
            "gate": ApprovalGate.IDEA_APPROVAL.value,
            "decision": ApprovalDecision.APPROVED.value,
            "target_type": "ProductConcept",
            "target_id": str(concept_id),
            "target_version": 1,
        }

        first = await client.post(f"/api/v1/workflows/{workflow_id}/approvals", json=body)
        # A double-clicked button or a redelivered Telegram callback.
        second = await client.post(f"/api/v1/workflows/{workflow_id}/approvals", json=body)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

        async with UnitOfWork(session_factory) as uow:
            history = await uow.approvals.history(workflow_id, gate=ApprovalGate.IDEA_APPROVAL)
            assert len(history) == 1

    async def test_approving_a_superseded_version_is_refused(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        concept_id = await _seed_concept(session_factory, workflow_id)

        # The owner revises the prompt, so version 1 is no longer what a
        # reviewer would be looking at.
        revised = await client.post(
            f"/api/v1/workflows/{workflow_id}/concepts/{concept_id}/revise",
            json={
                "positive_prompt": "rustic sunflower, heavier texture",
                "negative_prompt": "background, mockup",
                "change_note": "More texture",
            },
        )
        assert revised.json()["version"] == 2
        await _move_to_idea_review(session_factory, workflow_id)

        stale = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
                "target_type": "ProductConcept",
                "target_id": str(concept_id),
                "target_version": 1,
            },
        )

        assert stale.status_code == 409
        assert stale.json()["type"].endswith("concurrent-modification")

    async def test_a_flagged_concept_cannot_be_approved(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        concept_id = await _seed_concept(session_factory, workflow_id, risk_level=RiskLevel.HIGH)
        await _move_to_idea_review(session_factory, workflow_id)

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
                "target_type": "ProductConcept",
                "target_id": str(concept_id),
                "target_version": 1,
            },
        )

        assert response.status_code == 409
        assert response.json()["type"].endswith("unresolved-risk")

    async def test_a_flagged_concept_can_still_be_rejected(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        concept_id = await _seed_concept(session_factory, workflow_id, risk_level=RiskLevel.HIGH)
        await _move_to_idea_review(session_factory, workflow_id)

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.REJECTED.value,
                "target_type": "ProductConcept",
                "target_id": str(concept_id),
                "target_version": 1,
            },
        )

        assert response.status_code == 201
        async with UnitOfWork(session_factory) as uow:
            concept = await uow.concepts.get(concept_id)
            assert concept is not None
            assert concept.status == ConceptStatus.REJECTED

    async def test_a_concept_from_another_workflow_is_not_approvable(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        other_workflow = await _create_workflow(client)
        foreign_concept = await _seed_concept(session_factory, other_workflow)
        await _move_to_idea_review(session_factory, workflow_id)

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/approvals",
            json={
                "gate": ApprovalGate.IDEA_APPROVAL.value,
                "decision": ApprovalDecision.APPROVED.value,
                "target_type": "ProductConcept",
                "target_id": str(foreign_concept),
                "target_version": 1,
            },
        )

        assert response.status_code == 404


class TestRevisionRescansRisk:
    async def test_a_revision_introducing_a_brand_raises_the_risk_flag(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        concept_id = await _seed_concept(session_factory, workflow_id)

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/concepts/{concept_id}/revise",
            json={
                "positive_prompt": "sunflower tumbler",
                "negative_prompt": "background",
                "exact_slogan": "Just Do It, Nike style",
                "change_note": "Added a slogan",
            },
        )

        assert response.status_code == 201
        async with UnitOfWork(session_factory) as uow:
            concept = await uow.concepts.get(concept_id)
            assert concept is not None
            assert concept.risk_level == RiskLevel.HIGH
            assert concept.risk_note is not None
            assert "nike" in concept.risk_note.lower()

    async def test_a_clean_revision_lowers_the_flag(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        workflow_id = await _create_workflow(client)
        concept_id = await _seed_concept(session_factory, workflow_id, risk_level=RiskLevel.HIGH)

        response = await client.post(
            f"/api/v1/workflows/{workflow_id}/concepts/{concept_id}/revise",
            json={
                "positive_prompt": "sunflower tumbler",
                "negative_prompt": "background",
                "exact_slogan": "Slow Mornings",
                "change_note": "Removed the brand reference",
            },
        )

        assert response.status_code == 201
        async with UnitOfWork(session_factory) as uow:
            concept = await uow.concepts.get(concept_id)
            assert concept is not None
            assert concept.risk_level == RiskLevel.LOW
