"""The development fixtures load, and say what they are."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ConceptOrigin, IdeaMode
from app.domain.workflow import ApprovalDecision, RunStatus
from app.fixtures import DEV_DATA_MARKER, FIXTURE_IDS, seed_development_data
from app.fixtures.dev_seed import USER_IDEA_TEXT

pytestmark = pytest.mark.integration


@pytest.fixture
async def seeded(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> async_sessionmaker[AsyncSession]:
    await seed_development_data(session_factory)
    return session_factory


class TestSeeding:
    async def test_creates_one_workflow_per_idea_mode(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        async with UnitOfWork(seeded) as uow:
            modes = set()
            for key in (
                "workflow_market_led",
                "workflow_user_idea",
                "workflow_hybrid",
            ):
                workflow = await uow.workflows.get(FIXTURE_IDS[key])
                assert workflow is not None
                modes.add(workflow.idea_mode)
            assert modes == set(IdeaMode)

    async def test_is_idempotent(self, seeded: async_sessionmaker[AsyncSession]) -> None:
        """Re-running must not duplicate the history."""
        async with UnitOfWork(seeded) as uow:
            before = await uow.workflows.count()
        await seed_development_data(seeded)
        async with UnitOfWork(seeded) as uow:
            assert await uow.workflows.count() == before

    async def test_original_idea_is_preserved_verbatim(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        async with UnitOfWork(seeded) as uow:
            idea = await uow.ideas.get_for_workflow(FIXTURE_IDS["workflow_user_idea"])
            assert idea is not None
            # Exactly what the fixture "owner" wrote, after a revision exists.
            assert idea.original_text == USER_IDEA_TEXT
            assert idea.revision_count == 1
            assert idea.current_text != idea.original_text

    async def test_market_led_workflow_has_no_original_idea(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        async with UnitOfWork(seeded) as uow:
            idea = await uow.ideas.get_for_workflow(FIXTURE_IDS["workflow_market_led"])
            assert idea is None

    async def test_hybrid_holds_all_three_concept_origins(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        async with UnitOfWork(seeded) as uow:
            concepts = await uow.concepts.list_for_workflow(FIXTURE_IDS["workflow_hybrid"])
            assert {concept.origin for concept in concepts} == set(ConceptOrigin)

    async def test_optimized_concepts_are_stored_separately(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        async with UnitOfWork(seeded) as uow:
            idea = await uow.ideas.get_for_workflow(FIXTURE_IDS["workflow_user_idea"])
            concepts = await uow.concepts.list_for_workflow(FIXTURE_IDS["workflow_user_idea"])
            assert idea is not None
            assert concepts
            for concept in concepts:
                assert concept.original_idea_id == idea.id
                # The concept is a different row with different words.
                assert concept.title != idea.original_text

    async def test_prompt_versions_are_kept(self, seeded: async_sessionmaker[AsyncSession]) -> None:
        async with UnitOfWork(seeded) as uow:
            concepts = await uow.concepts.list_for_workflow(FIXTURE_IDS["workflow_user_idea"])
            prompts = await uow.concepts.prompts(concepts[0].id)
            assert [prompt.version for prompt in prompts] == [1, 2]
            assert prompts[0].negative_prompt

    async def test_approval_history_keeps_the_rejection(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        async with UnitOfWork(seeded) as uow:
            history = await uow.approvals.history(FIXTURE_IDS["workflow_hybrid"])
            decisions = [approval.decision for approval in history]
            assert decisions == [
                ApprovalDecision.REJECTED,
                ApprovalDecision.APPROVED,
            ]

    async def test_transitions_are_recorded(self, seeded: async_sessionmaker[AsyncSession]) -> None:
        async with UnitOfWork(seeded) as uow:
            transitions = await uow.workflows.transitions(FIXTURE_IDS["workflow_market_led"])
            assert transitions[0].from_state is None
            assert transitions[-1].to_state is RunStatus.IDEA_REVIEW

    async def test_cost_entries_exist_and_are_free(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        """Fake providers cost nothing, but still produce ledger entries."""
        async with UnitOfWork(seeded) as uow:
            usage = await uow.costs.list_for_workflow(FIXTURE_IDS["workflow_user_idea"])
            assert len(usage) == 2
            total = await uow.costs.total_for_workflow(FIXTURE_IDS["workflow_user_idea"])
            assert total.is_zero

    async def test_audit_events_exist(self, seeded: async_sessionmaker[AsyncSession]) -> None:
        async with UnitOfWork(seeded) as uow:
            events = await uow.audit.for_workflow(FIXTURE_IDS["workflow_hybrid"])
            assert events


class TestFixturesAreHonest:
    async def test_every_workflow_is_marked_as_development_data(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        async with UnitOfWork(seeded) as uow:
            for key in (
                "workflow_market_led",
                "workflow_user_idea",
                "workflow_hybrid",
            ):
                workflow = await uow.workflows.get(FIXTURE_IDS[key])
                assert workflow is not None
                assert DEV_DATA_MARKER in workflow.name

    async def test_evidence_is_labelled_and_invents_no_numbers(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        import re

        import sqlalchemy

        from app.infrastructure.models import ResearchEvidence

        number_like = re.compile(
            r"\b\d[\d,.]*\s*(sales|searches|search volume|revenue|orders|buyers|"
            r"per month|/mo|%)\b",
            re.IGNORECASE,
        )

        async with UnitOfWork(seeded) as uow:
            rows = (await uow.session.execute(sqlalchemy.select(ResearchEvidence))).scalars().all()
            assert rows
            for row in rows:
                assert DEV_DATA_MARKER in row.observation
                assert not number_like.search(row.observation)
                assert row.inference is not None
                assert not number_like.search(row.inference)

    async def test_no_concept_claims_low_risk(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        """No IP screening was performed, so nothing may look cleared."""
        from app.domain.workflow import RiskLevel

        async with UnitOfWork(seeded) as uow:
            for key in (
                "workflow_market_led",
                "workflow_user_idea",
                "workflow_hybrid",
            ):
                for concept in await uow.concepts.list_for_workflow(FIXTURE_IDS[key]):
                    assert concept.risk_level is RiskLevel.UNKNOWN

    async def test_research_runs_are_low_confidence(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        import sqlalchemy

        from app.domain.enums import ConfidenceLevel
        from app.infrastructure.models import ResearchRun

        async with UnitOfWork(seeded) as uow:
            runs = (await uow.session.execute(sqlalchemy.select(ResearchRun))).scalars().all()
            assert runs
            for run in runs:
                assert run.confidence is ConfidenceLevel.LOW
                assert len(run.query_angles) >= 3

    async def test_low_scoring_concept_is_kept(
        self, seeded: async_sessionmaker[AsyncSession]
    ) -> None:
        from decimal import Decimal

        async with UnitOfWork(seeded) as uow:
            concepts = await uow.concepts.list_for_workflow(FIXTURE_IDS["workflow_market_led"])
            scores = [concept.score for concept in concepts]
            assert Decimal("2.20") in scores
            assert len(concepts) == 3
