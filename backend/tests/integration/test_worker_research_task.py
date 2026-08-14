"""The research actor, end to end against a real database.

Lives in the backend integration suite because that is where a migrated
PostgreSQL is available; the worker's own suite must stay database-free. Every
provider here is the deterministic fake, so no paid call is possible.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import dramatiq
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from worker.tasks import _run_research_async, run_research_task

from app.application.unit_of_work import UnitOfWork
from app.application.workflows import (
    CreateWorkflowCommand,
    SubmitIdeaCommand,
    create_workflow,
    submit_original_idea,
)
from app.domain.enums import ConceptStatus, ConfidenceLevel, IdeaMode
from app.domain.workflow import JobStatus, RunStatus
from app.infrastructure.models import User
from app.ports.errors import ProviderError, ProviderErrorKind
from app.settings import get_settings

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def worker_settings(test_env: dict[str, str]) -> Iterator[None]:
    """Point the actor's own ``get_settings()`` at the test database.

    The actor builds its own engine rather than being handed one, so the cache
    is cleared around each test; otherwise it would keep whatever settings the
    first test that touched it created.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _queued_run(
    session_factory: async_sessionmaker[AsyncSession],
    owner_id: uuid.UUID,
    *,
    idea_mode: IdeaMode = IdeaMode.MARKET_LED,
    idea_text: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """A workflow in RESEARCH_QUEUED with one queued run, as the API leaves it."""
    async with UnitOfWork(session_factory) as uow:
        workflow = await create_workflow(
            uow,
            CreateWorkflowCommand(
                owner_id=owner_id,
                idea_mode=idea_mode,
                name="Sleepy fox mugs",
                target_country="US",
                output_language="en",
                intended_product_uses=["mug"],
            ),
        )
        if idea_text is not None:
            await submit_original_idea(
                uow,
                SubmitIdeaCommand(
                    workflow_id=workflow.id,
                    owner_id=owner_id,
                    original_text=idea_text,
                    slogan="Slow Mornings",
                ),
            )
        await uow.workflows.transition(
            workflow,
            to_state=RunStatus.RESEARCH_QUEUED,
            expected_version=workflow.version,
            reason="Queued by test",
            actor="test",
        )
        run = await uow.research.add_run(workflow.id)
        await uow.commit()
        return workflow.id, run.id


class TestResearchRunSucceeds:
    async def test_a_run_produces_evidence_clusters_and_ranked_concepts(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        owner: User,
    ) -> None:
        workflow_id, run_id = await _queued_run(session_factory, owner.id)

        await _run_research_async(workflow_id, run_id)

        async with UnitOfWork(session_factory) as uow:
            run = await uow.research.get_run(run_id)
            assert run is not None
            assert run.status == JobStatus.SUCCEEDED
            assert run.completed_at is not None
            assert run.confidence in set(ConfidenceLevel)

            # At least three distinct buyer-intent angles (root CLAUDE.md).
            assert len(set(run.query_angles)) >= 3

            evidence = await uow.research.get_evidence_for_run(run_id)
            assert evidence
            for item in evidence:
                # An observation with no query behind it cannot be reviewed, so
                # the query that found the source is stored with it.
                assert item.search_query
                assert item.query_angle in set(run.query_angles)
                assert item.source_url
                assert item.observation

            clusters = await uow.research.get_keyword_clusters_for_run(run_id)
            assert clusters
            assert all(cluster.primary_phrase for cluster in clusters)

            concepts = await uow.concepts.list_for_workflow(workflow_id)
            assert len(concepts) >= 3
            for concept in concepts:
                assert concept.research_run_id == run_id
                # Outside 1..5 would mean the weighting drifted from the
                # documented formula.
                assert 1.0 <= (concept.score or 0.0) <= 5.0
                prompts = await uow.concepts.prompts(concept.id)
                assert len(prompts) == 1
                assert prompts[0].version == 1
                # The prompt contract: something to draw, and an explicit list
                # of what must never appear.
                assert prompts[0].positive_prompt
                assert prompts[0].negative_prompt

            # One concept is shortlisted for the owner to look at first.
            shortlisted = [c for c in concepts if c.status == ConceptStatus.SHORTLISTED]
            assert len(shortlisted) == 1

            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None
            # Stops at the human gate; it must never walk past IDEA_REVIEW.
            assert workflow.state == RunStatus.IDEA_REVIEW

    async def test_a_fake_run_is_ledgered_at_zero_cost(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        owner: User,
    ) -> None:
        workflow_id, run_id = await _queued_run(session_factory, owner.id)

        await _run_research_async(workflow_id, run_id)

        async with UnitOfWork(session_factory) as uow:
            usages = await uow.costs.list_for_workflow(workflow_id)
            assert len(usages) == 1
            # Still ledgered in fake mode: a missing row would hide the
            # operation from the audit trail, and zero is the honest cost.
            assert usages[0].actual_cost_minor == 0
            assert usages[0].idempotency_key == f"cost-research-synthesis-{run_id}"

    async def test_a_user_idea_run_ties_its_concepts_to_the_original_idea(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        owner: User,
    ) -> None:
        idea_text = "A sleepy fox curled around a steaming mug"
        workflow_id, run_id = await _queued_run(
            session_factory,
            owner.id,
            idea_mode=IdeaMode.USER_IDEA,
            idea_text=idea_text,
        )

        await _run_research_async(workflow_id, run_id)

        async with UnitOfWork(session_factory) as uow:
            original = await uow.ideas.get_for_workflow(workflow_id)
            assert original is not None
            # The owner's wording survives the run untouched: that is the whole
            # promise of user-idea mode.
            assert original.original_text == idea_text

            concepts = await uow.concepts.list_for_workflow(workflow_id)
            faithful = [c for c in concepts if c.original_idea_id == original.id]
            assert faithful, "a user-idea run must link its concepts to the original idea"


class TestResearchRunIsIdempotent:
    async def test_a_redelivered_message_does_not_run_twice(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        owner: User,
    ) -> None:
        workflow_id, run_id = await _queued_run(session_factory, owner.id)

        await _run_research_async(workflow_id, run_id)
        async with UnitOfWork(session_factory) as uow:
            first_concepts = len(await uow.concepts.list_for_workflow(workflow_id))
            first_usages = len(await uow.costs.list_for_workflow(workflow_id))
            first_evidence = len(await uow.research.get_evidence_for_run(run_id))

        # At-least-once delivery: the broker hands us the same message again.
        await _run_research_async(workflow_id, run_id)

        async with UnitOfWork(session_factory) as uow:
            assert len(await uow.concepts.list_for_workflow(workflow_id)) == first_concepts
            assert len(await uow.research.get_evidence_for_run(run_id)) == first_evidence
            # Billed once, not twice.
            assert len(await uow.costs.list_for_workflow(workflow_id)) == first_usages
            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None
            assert workflow.state == RunStatus.IDEA_REVIEW

    async def test_a_message_for_a_missing_run_is_ignored(
        self, session_factory: async_sessionmaker[AsyncSession], owner: User
    ) -> None:
        workflow_id, _ = await _queued_run(session_factory, owner.id)

        # A message naming a run that was never persisted, or was purged.
        await _run_research_async(workflow_id, uuid.uuid4())

        async with UnitOfWork(session_factory) as uow:
            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None
            assert workflow.state == RunStatus.RESEARCH_QUEUED


class TestResearchRunStopsOnBudget:
    async def test_an_exhausted_budget_stops_the_run_before_any_provider_call(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        owner: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workflow_id, run_id = await _queued_run(session_factory, owner.id)
        async with UnitOfWork(session_factory) as uow:
            owner_settings = await uow.owner_settings.create_defaults(owner.id)
            owner_settings.daily_budget_minor = 0
            owner_settings.monthly_budget_minor = 0
            await uow.commit()

        # Live mode gives the run a non-zero estimate, which a zero budget
        # cannot absorb. The API checked this too, but the ledger can move
        # between queueing and delivery.
        monkeypatch.setenv("PROVIDER_MODE", "live")
        # Live settings refuse to load without one; a placeholder is enough
        # because the run is refused long before anything is sent.
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "not-a-real-token")
        get_settings.cache_clear()

        with pytest.raises(ProviderError) as caught:
            await _run_research_async(workflow_id, run_id)

        # Budget is never retryable: waiting does not make the call cheaper.
        assert caught.value.kind == ProviderErrorKind.BUDGET_EXCEEDED
        assert not caught.value.is_retryable

        async with UnitOfWork(session_factory) as uow:
            # Nothing was bought and nothing moved forward.
            assert await uow.costs.list_for_workflow(workflow_id) == []
            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None
            assert workflow.state == RunStatus.RESEARCH_QUEUED


# The actor entrypoint calls ``asyncio.run`` itself, so these are ordinary
# synchronous tests: an async one would already own the loop.


def test_a_permanent_provider_error_marks_the_run_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id, run_id = uuid.uuid4(), uuid.uuid4()
    marked: list[tuple[uuid.UUID, uuid.UUID, str]] = []

    async def _fail(_workflow_id: uuid.UUID, _run_id: uuid.UUID) -> None:
        raise ProviderError(
            kind=ProviderErrorKind.INVALID_REQUEST,
            provider="openai",
            operation="generate",
            message="model refused the request",
        )

    async def _record(wf_id: uuid.UUID, r_id: uuid.UUID, reason: str) -> None:
        marked.append((wf_id, r_id, reason))

    monkeypatch.setattr("worker.tasks._run_research_async", _fail)
    monkeypatch.setattr("worker.tasks._mark_failure_async", _record)

    # A permanent error must not raise: retrying a 4xx spends money to fail
    # again. The run is recorded as failed and the message is done with.
    run_research_task(str(workflow_id), str(run_id))

    assert marked == [(workflow_id, run_id, "model refused the request")]


def test_a_transient_provider_error_asks_dramatiq_to_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fail(_workflow_id: uuid.UUID, _run_id: uuid.UUID) -> None:
        raise ProviderError(
            kind=ProviderErrorKind.RATE_LIMITED,
            provider="tavily",
            operation="search",
            message="slow down",
            retry_after_seconds=7.0,
        )

    monkeypatch.setattr("worker.tasks._run_research_async", _fail)

    with pytest.raises(dramatiq.errors.Retry) as caught:
        run_research_task(str(uuid.uuid4()), str(uuid.uuid4()))

    # The provider said when to come back; we honour it rather than guessing.
    assert caught.value.delay == 7000


def test_worker_and_broker_initialization() -> None:
    # 1. Verify broker initialization does not duplicate middleware
    from worker.broker import build_broker
    test_broker = build_broker("redis://localhost:6379/0", "test_namespace")
    middleware_types = [type(m) for m in test_broker.middleware]
    assert len(middleware_types) == len(set(middleware_types)), f"Duplicate middleware detected: {middleware_types}"

    # 2. Verify run_research_task is registered on the configured broker
    broker = dramatiq.get_broker()
    declared_actors = broker.get_declared_actors()
    assert "run_research_task" in declared_actors, f"run_research_task not registered! Actors: {declared_actors}"

    # 3. Verify outbox message event_type can find the actor
    actor = broker.get_actor("run_research_task")
    assert actor is not None
    assert actor.actor_name == "run_research_task"


class TestResearchGeminiTransition:
    async def test_missing_gemini_credential_raises_authentication_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        owner: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workflow_id, run_id = await _queued_run(session_factory, owner.id)

        # Force live mode
        monkeypatch.setenv("PROVIDER_MODE", "live")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "not-a-real-token")
        # Ensure tavily key is set so it doesn't fail on tavily credential
        monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily-key")
        get_settings.cache_clear()

        # In this test, we do not save any GEMINI credential for the user.
        # It should fail with authentication error for gemini.
        with pytest.raises(ProviderError) as caught:
            await _run_research_async(workflow_id, run_id)

        assert caught.value.kind == ProviderErrorKind.AUTHENTICATION
        assert caught.value.provider == "gemini"
        assert "Gemini API Key is missing or invalid in credentials" in caught.value.message

    async def test_openai_credential_not_required_and_tavily_gemini_success(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        owner: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.providers.gemini import GeminiSynthesisAdapter
        from app.providers.search import TavilySearchAdapter
        from app.ports.providers import SearchResult, TextResponse
        from datetime import UTC, datetime
        import json
        import sqlalchemy as sa
        from app.domain.enums import ProviderName
        from app.api.dependencies import build_credential_cipher
        from app.domain.money import Money

        settings = get_settings()

        async def mock_search(self, query: Any) -> list[SearchResult]:
            return [
                SearchResult(
                    url="https://example.com",
                    title="Mock Result",
                    observation="Found some good design ideas",
                    source_type="trends",
                    captured_at=datetime.now(UTC),
                )
            ]

        async def mock_generate(self, request: Any) -> TextResponse:
            payload = {
                "confidence": "high",
                "proposed_test": None,
                "keyword_clusters": [
                    {
                        "primary_phrase": "mock phrase",
                        "attributes": ["mock"],
                        "recipient_occasion_terms": ["mock"],
                        "use_case_terms": ["mock"],
                        "competition_level": "thin",
                        "competition_note": "very thin",
                        "relevance_rank": 95,
                    }
                ],
                "concepts": [
                    {
                        "title": "Mock Title",
                        "description": "Mock Description",
                        "differentiation": "Mock Diff",
                        "target_buyer": "Mock Buyer",
                        "buyer_use_case": "Mock Use Case",
                        "seasonality": "evergreen",
                        "risk_level": "low",
                        "risk_note": "No risk",
                        "score_breakdown": {
                            "demand": 5,
                            "competition_opportunity": 5,
                            "seasonal_timing": 5,
                            "buyer_clarity": 5,
                            "differentiation": 5,
                            "product_versatility": 5,
                            "ip_safety": 5,
                        },
                        "score_explanation": "Perfect score",
                        "fidelity": "High",
                        "origin": "market",
                        "prompt": {
                            "positive_prompt": "positive",
                            "negative_prompt": "negative",
                            "typography_instructions": "typo",
                            "exact_slogan": "slogan",
                            "intended_product_uses": ["mug"],
                            "style_notes": "style",
                            "palette": "palette",
                            "post_generation_checklist": ["check"],
                            "generation_metadata": {},
                        }
                    }
                ]
            }
            return TextResponse(
                text=json.dumps(payload),
                input_tokens=100,
                output_tokens=200,
                model="gemini-1.5-flash",
            )

        monkeypatch.setattr(TavilySearchAdapter, "search", mock_search)
        monkeypatch.setattr(GeminiSynthesisAdapter, "generate", mock_generate)

        # Save a GEMINI credential to the database but NO openai credential
        cipher = build_credential_cipher(settings)
        encrypted_gemini = cipher.encrypt("real-gemini-key")

        async with UnitOfWork(session_factory) as uow:
            from app.infrastructure.models.owner_settings import ProviderCredential
            # Delete any existing OpenAI credential for this owner to prove it is not required
            await uow.session.execute(
                sa.delete(ProviderCredential).where(
                    ProviderCredential.user_id == owner.id,
                    ProviderCredential.provider == ProviderName.OPENAI
                )
            )
            # Add Gemini credential
            gemini_cred = ProviderCredential(
                user_id=owner.id,
                provider=ProviderName.GEMINI,
                ciphertext=encrypted_gemini,
                key_version=cipher.key_version,
                masked_value="••••••••1234",
            )
            await uow.session.merge(gemini_cred)
            await uow.commit()

        workflow_id, run_id = await _queued_run(session_factory, owner.id)

        # Verify initial states
        async with UnitOfWork(session_factory) as uow:
            workflow = await uow.workflows.get(workflow_id)
            assert workflow.state == RunStatus.RESEARCH_QUEUED
            run = await uow.research.get_run(run_id)
            assert run.status == JobStatus.QUEUED

        # Force live mode
        monkeypatch.setenv("PROVIDER_MODE", "live")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "not-a-real-token")
        monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily-key")
        get_settings.cache_clear()

        # Run the research task
        await _run_research_async(workflow_id, run_id)

        # Verify success states and transition
        async with UnitOfWork(session_factory) as uow:
            # 1. State transitioned: RESEARCH_QUEUED -> IDEA_REVIEW
            workflow = await uow.workflows.get(workflow_id)
            assert workflow.state == RunStatus.IDEA_REVIEW

            # 2. Run completed successfully
            run = await uow.research.get_run(run_id)
            assert run.status == JobStatus.SUCCEEDED

            # 3. Concepts and evidence were created
            concepts = await uow.concepts.list_for_workflow(workflow_id)
            assert len(concepts) == 1
            assert concepts[0].title == "Mock Title"

            # 4. Ledger cost attributed to GEMINI
            costs = await uow.costs.list_for_workflow(workflow_id)
            assert len(costs) == 1
            assert costs[0].provider == ProviderName.GEMINI


