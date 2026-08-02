"""Repository behaviour against a real database."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import (
    AuditAction,
    ConceptOrigin,
    ConceptStatus,
    CostStatus,
    IdeaMode,
    ProviderName,
)
from app.domain.errors import ConcurrentModificationError, ImmutableFieldError
from app.domain.ideas import is_faithful_to_original, normalize_idea_text
from app.domain.money import Money
from app.domain.workflow import (
    ApprovalDecision,
    ApprovalGate,
    IllegalTransitionError,
    RunStatus,
)
from app.infrastructure.models import (
    OriginalIdea,
    ProductConcept,
    ProductWorkflow,
    User,
)

pytestmark = pytest.mark.integration


async def _workflow(
    uow: UnitOfWork, owner: User, mode: IdeaMode = IdeaMode.USER_IDEA
) -> ProductWorkflow:
    workflow = ProductWorkflow(
        owner_id=owner.id,
        idea_mode=mode,
        name="Test workflow",
        target_country="US",
        output_language="en",
        intended_product_uses=["mug"],
        state=RunStatus.DRAFT,
        version=1,
    )
    await uow.workflows.add(workflow)
    await uow.workflows.record_initial_state(workflow)
    await uow.commit()
    return workflow


class TestWorkflowRepository:
    async def test_create_and_fetch(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        fetched = await uow.workflows.get(workflow.id)
        assert fetched is not None
        assert fetched.idea_mode is IdeaMode.USER_IDEA
        assert fetched.state is RunStatus.DRAFT
        assert fetched.version == 1

    @pytest.mark.parametrize("mode", list(IdeaMode))
    async def test_every_idea_mode_persists(
        self, uow: UnitOfWork, owner: User, mode: IdeaMode
    ) -> None:
        workflow = await _workflow(uow, owner, mode)
        fetched = await uow.workflows.get(workflow.id)
        assert fetched is not None
        assert fetched.idea_mode is mode

    async def test_transition_bumps_version_and_records_a_row(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        workflow = await _workflow(uow, owner)
        await uow.workflows.transition(
            workflow,
            to_state=RunStatus.RESEARCH_QUEUED,
            expected_version=1,
            reason="research_enqueued",
        )
        await uow.commit()

        assert workflow.state is RunStatus.RESEARCH_QUEUED
        assert workflow.version == 2

        transitions = await uow.workflows.transitions(workflow.id)
        assert [t.to_state for t in transitions] == [
            RunStatus.DRAFT,
            RunStatus.RESEARCH_QUEUED,
        ]
        assert transitions[0].from_state is None
        assert transitions[-1].resulting_version == 2

    async def test_illegal_transition_is_refused_before_any_write(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        workflow = await _workflow(uow, owner)
        with pytest.raises(IllegalTransitionError):
            await uow.workflows.transition(
                workflow,
                to_state=RunStatus.ETSY_DRAFT_CREATED,
                expected_version=1,
                reason="cheating",
            )
        await uow.rollback()

        fetched = await uow.workflows.get(workflow.id)
        assert fetched is not None
        assert fetched.state is RunStatus.DRAFT
        assert fetched.version == 1

    async def test_stale_version_is_rejected(self, uow: UnitOfWork, owner: User) -> None:
        """Compare-and-set: a decision made against version 1 must not apply
        after someone else moved the workflow to version 2."""
        workflow = await _workflow(uow, owner)
        await uow.workflows.transition(
            workflow,
            to_state=RunStatus.RESEARCH_QUEUED,
            expected_version=1,
            reason="first",
        )
        await uow.commit()

        with pytest.raises(ConcurrentModificationError) as excinfo:
            await uow.workflows.transition(
                workflow,
                to_state=RunStatus.RESEARCHING,
                expected_version=1,  # stale
                reason="second",
            )
        assert excinfo.value.expected_version == 1
        assert excinfo.value.actual_version == 2

    async def test_list_filters_and_counts(self, uow: UnitOfWork, owner: User) -> None:
        first = await _workflow(uow, owner, IdeaMode.MARKET_LED)
        await _workflow(uow, owner, IdeaMode.HYBRID)

        await uow.workflows.transition(
            first,
            to_state=RunStatus.RESEARCH_QUEUED,
            expected_version=1,
            reason="enqueued",
        )
        await uow.commit()

        drafts = await uow.workflows.list(state=RunStatus.DRAFT)
        assert len(drafts) == 1
        assert await uow.workflows.count() == 2
        assert await uow.workflows.count(state=RunStatus.RESEARCH_QUEUED) == 1

    async def test_archived_workflows_are_hidden_by_default(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        from app.infrastructure.models.base import utc_now

        workflow = await _workflow(uow, owner)
        workflow.archived_at = utc_now()
        await uow.commit()

        assert await uow.workflows.count() == 0
        assert await uow.workflows.count(include_archived=True) == 1


class TestOriginalIdeaImmutability:
    async def test_original_text_survives_revisions(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        original = "A sleepy fox curled around a steaming mug."

        idea = OriginalIdea(
            workflow_id=workflow.id,
            original_text=original,
            normalized_text=normalize_idea_text(original),
        )
        await uow.ideas.add(idea)
        await uow.commit()

        await uow.ideas.add_revision(
            idea, revised_text=f"{original} Muted palette.", note="Palette note"
        )
        await uow.ideas.add_revision(
            idea, revised_text=f"{original} Muted palette, no orange.", note="Refined"
        )
        await uow.commit()

        reloaded = await uow.ideas.get_for_workflow(workflow.id)
        assert reloaded is not None
        # The promise: the owner's first words are still exactly there.
        assert reloaded.original_text == original
        assert is_faithful_to_original(original, reloaded.original_text)
        assert reloaded.revision_count == 2
        assert reloaded.current_text.endswith("no orange.")

    async def test_revisions_are_numbered_and_ordered(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        idea = OriginalIdea(
            workflow_id=workflow.id,
            original_text="Original text here",
            normalized_text=normalize_idea_text("Original text here"),
        )
        await uow.ideas.add(idea)
        for index in range(3):
            await uow.ideas.add_revision(idea, revised_text=f"Revision {index}")
        await uow.commit()

        revisions = await uow.ideas.revisions(idea.id)
        assert [r.revision_number for r in revisions] == [1, 2, 3]

    async def test_editing_original_text_is_refused(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        idea = OriginalIdea(
            workflow_id=workflow.id,
            original_text="Do not overwrite me",
            normalized_text=normalize_idea_text("Do not overwrite me"),
        )
        await uow.ideas.add(idea)
        await uow.commit()

        idea.original_text = "An optimised rewrite"
        with pytest.raises(ImmutableFieldError, match="original_text"):
            await uow.ideas.add_revision(idea, revised_text="anything")

    async def test_one_idea_per_workflow(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        for _ in range(2):
            uow.session.add(
                OriginalIdea(
                    workflow_id=workflow.id,
                    original_text="Some idea text",
                    normalized_text="some idea text",
                )
            )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()

    async def test_duplicate_revision_number_is_refused(self, uow: UnitOfWork, owner: User) -> None:
        from app.infrastructure.models import OriginalIdeaRevision

        workflow = await _workflow(uow, owner)
        idea = OriginalIdea(
            workflow_id=workflow.id,
            original_text="Some idea text",
            normalized_text="some idea text",
        )
        await uow.ideas.add(idea)
        for _ in range(2):
            uow.session.add(
                OriginalIdeaRevision(
                    idea_id=idea.id,
                    revision_number=1,
                    revised_text="dup",
                    normalized_text="dup",
                )
            )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()


class TestConceptsAndPrompts:
    async def _concept(
        self, uow: UnitOfWork, workflow: ProductWorkflow, origin: ConceptOrigin
    ) -> ProductConcept:
        concept = ProductConcept(
            workflow_id=workflow.id,
            title="A concept",
            description="Description",
            origin=origin,
            differentiation="A real point of difference",
        )
        await uow.concepts.add(concept)
        await uow.commit()
        return concept

    @pytest.mark.parametrize("origin", list(ConceptOrigin))
    async def test_every_origin_persists(
        self, uow: UnitOfWork, owner: User, origin: ConceptOrigin
    ) -> None:
        workflow = await _workflow(uow, owner, IdeaMode.HYBRID)
        concept = await self._concept(uow, workflow, origin)
        fetched = await uow.concepts.get(concept.id)
        assert fetched is not None
        assert fetched.origin is origin

    async def test_user_concept_links_back_to_the_preserved_idea(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        workflow = await _workflow(uow, owner)
        original = "The owner's own words"
        idea = OriginalIdea(
            workflow_id=workflow.id,
            original_text=original,
            normalized_text=normalize_idea_text(original),
        )
        await uow.ideas.add(idea)

        concept = ProductConcept(
            workflow_id=workflow.id,
            original_idea_id=idea.id,
            title="Optimised title that reads nothing like the original",
            description="Rewritten for the marketplace",
            origin=ConceptOrigin.USER,
            differentiation="Texture-led rendering",
        )
        await uow.concepts.add(concept)
        await uow.commit()

        # The optimised concept exists *and* the original is untouched.
        assert concept.original_idea_id == idea.id
        assert not is_faithful_to_original(original, concept.title)
        reloaded = await uow.ideas.get_for_workflow(workflow.id)
        assert reloaded is not None
        assert reloaded.original_text == original

    async def test_prompt_versions_increment_and_persist(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        workflow = await _workflow(uow, owner)
        concept = await self._concept(uow, workflow, ConceptOrigin.USER)

        first = await uow.concepts.add_prompt_version(
            concept, positive_prompt="v1 positive", negative_prompt="v1 negative"
        )
        second = await uow.concepts.add_prompt_version(
            concept,
            positive_prompt="v2 positive",
            negative_prompt="v2 negative",
            change_note="Tighter composition",
        )
        await uow.commit()

        assert (first.version, second.version) == (1, 2)
        prompts = await uow.concepts.prompts(concept.id)
        assert [p.version for p in prompts] == [1, 2]
        # Version 1 is untouched, so an asset made from it stays traceable.
        assert prompts[0].positive_prompt == "v1 positive"

    async def test_duplicate_prompt_version_is_refused(self, uow: UnitOfWork, owner: User) -> None:
        from app.infrastructure.models import DesignPrompt

        workflow = await _workflow(uow, owner)
        concept = await self._concept(uow, workflow, ConceptOrigin.USER)
        for _ in range(2):
            uow.session.add(
                DesignPrompt(
                    concept_id=concept.id,
                    version=1,
                    positive_prompt="p",
                    negative_prompt="n",
                )
            )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()

    async def test_a_low_score_does_not_remove_a_user_concept(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        workflow = await _workflow(uow, owner)
        concept = ProductConcept(
            workflow_id=workflow.id,
            title="Owner's idea, scored poorly",
            description="Description",
            origin=ConceptOrigin.USER,
            differentiation="A real point of difference",
            score=Decimal("1.20"),
        )
        await uow.concepts.add(concept)
        await uow.commit()

        listed = await uow.concepts.list_for_workflow(workflow.id)
        assert [c.id for c in listed] == [concept.id]
        assert listed[0].status is ConceptStatus.PROPOSED

    async def test_score_outside_range_is_refused(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        uow.session.add(
            ProductConcept(
                workflow_id=workflow.id,
                title="Impossible score",
                description="Description",
                origin=ConceptOrigin.MARKET,
                differentiation="x",
                score=Decimal("9.99"),
            )
        )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()


class TestApprovalHistory:
    async def test_history_is_append_only(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        for to_state, reason in [
            (RunStatus.RESEARCH_QUEUED, "enqueued"),
            (RunStatus.RESEARCHING, "started"),
            (RunStatus.IDEA_REVIEW, "completed"),
        ]:
            await uow.workflows.transition(
                workflow,
                to_state=to_state,
                expected_version=workflow.version,
                reason=reason,
            )
        await uow.commit()

        rejected = await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.IDEA_APPROVAL,
            decision=ApprovalDecision.REJECTED,
            previous_state=RunStatus.IDEA_REVIEW,
            resulting_state=RunStatus.DRAFT,
            actor="owner",
            target_type="ProductWorkflow",
            comment="Not this one",
        )
        approved = await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.IDEA_APPROVAL,
            decision=ApprovalDecision.APPROVED,
            previous_state=RunStatus.IDEA_REVIEW,
            resulting_state=RunStatus.IDEA_APPROVED,
            actor="owner",
            target_type="ProductWorkflow",
        )
        await uow.commit()

        history = await uow.approvals.history(workflow.id)
        assert len(history) == 2
        # The rejection is still there, unchanged.
        assert history[0].id == rejected.id
        assert history[0].decision is ApprovalDecision.REJECTED
        assert history[0].comment == "Not this one"
        assert history[1].id == approved.id

    async def test_latest_decision_governs_the_gate(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.IDEA_APPROVAL,
            decision=ApprovalDecision.APPROVED,
            previous_state=RunStatus.IDEA_REVIEW,
            resulting_state=RunStatus.IDEA_APPROVED,
            actor="owner",
            target_type="ProductWorkflow",
        )
        await uow.commit()
        assert await uow.approvals.is_approved(workflow.id, ApprovalGate.IDEA_APPROVAL)

        # A later revision request revokes it.
        await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.IDEA_APPROVAL,
            decision=ApprovalDecision.REVISION_REQUESTED,
            previous_state=RunStatus.IDEA_REVIEW,
            resulting_state=RunStatus.RESEARCH_QUEUED,
            actor="owner",
            target_type="ProductWorkflow",
            revision_request="Try a warmer palette",
        )
        await uow.commit()
        assert not await uow.approvals.is_approved(workflow.id, ApprovalGate.IDEA_APPROVAL)

    async def test_pending_request_has_no_decided_at(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        approval = await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.IDEA_APPROVAL,
            decision=ApprovalDecision.PENDING,
            previous_state=RunStatus.IDEA_REVIEW,
            resulting_state=RunStatus.IDEA_REVIEW,
            actor="owner",
            target_type="ProductWorkflow",
        )
        await uow.commit()
        assert approval.decided_at is None

    async def test_revision_without_request_text_is_refused(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        """The database enforces it, not just the API."""
        workflow = await _workflow(uow, owner)
        with pytest.raises((IntegrityError, DBAPIError)):
            await uow.approvals.record(
                workflow=workflow,
                gate=ApprovalGate.IDEA_APPROVAL,
                decision=ApprovalDecision.REVISION_REQUESTED,
                previous_state=RunStatus.IDEA_REVIEW,
                resulting_state=RunStatus.RESEARCH_QUEUED,
                actor="owner",
                target_type="ProductWorkflow",
                revision_request=None,
            )
        await uow.rollback()

    async def test_approval_records_the_reviewed_version(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        workflow = await _workflow(uow, owner)
        target = uuid.uuid4()
        approval = await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.ARTWORK_APPROVAL,
            decision=ApprovalDecision.APPROVED,
            previous_state=RunStatus.ART_REVIEW,
            resulting_state=RunStatus.ARTWORK_APPROVED,
            actor="owner",
            target_type="DesignPrompt",
            target_id=target,
            target_version=2,
        )
        await uow.commit()
        assert approval.target_version == 2
        assert approval.target_id == target


class TestCostLedger:
    async def test_estimate_then_reconcile(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        usage = await uow.costs.record_estimate(
            workflow_id=workflow.id,
            provider=ProviderName.FAKE,
            service="fake-image-1",
            operation="image_generation",
            estimated=Money.from_decimal(Decimal("0.041")),
            output_units=1,
            unit_kind="images",
        )
        await uow.commit()
        assert usage.status is CostStatus.ESTIMATED
        assert usage.actual_cost_minor is None
        assert usage.effective_cost_minor == 4

        reconciled = await uow.costs.reconcile(usage.id, actual=Money.from_decimal(Decimal("0.05")))
        await uow.commit()
        assert reconciled.status is CostStatus.RECONCILED
        assert reconciled.actual_cost_minor == 5
        assert reconciled.effective_cost_minor == 5

    async def test_totals_are_exact(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        for amount in ["0.05", "0.041", "0.035", "0.01", "0.004"]:
            await uow.costs.record_estimate(
                workflow_id=workflow.id,
                provider=ProviderName.FAKE,
                service="svc",
                operation="op",
                estimated=Money.from_decimal(Decimal(amount)),
            )
        await uow.commit()

        total = await uow.costs.total_for_workflow(workflow.id)
        # 5 + 4 + 4 + 1 + 0 cents, computed in integers end to end.
        assert total.minor_units == 14
        assert total.to_decimal() == Decimal("0.14")

    async def test_per_operation_totals(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        for operation, amount in [
            ("image_generation", "0.041"),
            ("image_generation", "0.035"),
            ("text_synthesis", "0.008"),
        ]:
            await uow.costs.record_estimate(
                workflow_id=workflow.id,
                provider=ProviderName.FAKE,
                service="svc",
                operation=operation,
                estimated=Money.from_decimal(Decimal(amount)),
            )
        await uow.commit()

        by_operation = await uow.costs.total_by_operation(workflow.id)
        assert by_operation["image_generation"].minor_units == 8
        assert by_operation["text_synthesis"].minor_units == 1

    async def test_per_provider_total(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        await uow.costs.record_estimate(
            workflow_id=workflow.id,
            provider=ProviderName.FAKE,
            service="svc",
            operation="op",
            estimated=Money.from_decimal(Decimal("0.25")),
        )
        await uow.commit()
        assert (await uow.costs.total_for_provider(ProviderName.FAKE)).minor_units == 25
        assert (await uow.costs.total_for_provider(ProviderName.OPENAI)).minor_units == 0

    async def test_voided_entry_stops_counting(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        usage = await uow.costs.record_estimate(
            workflow_id=workflow.id,
            provider=ProviderName.FAKE,
            service="svc",
            operation="op",
            estimated=Money.from_decimal(Decimal("1.00")),
        )
        await uow.commit()
        assert (await uow.costs.total_for_workflow(workflow.id)).minor_units == 100

        await uow.costs.void(usage.id)
        await uow.commit()
        assert (await uow.costs.total_for_workflow(workflow.id)).minor_units == 0

    async def test_empty_ledger_totals_zero(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        assert (await uow.costs.total_for_workflow(workflow.id)).is_zero

    async def test_reconciled_row_requires_an_actual_amount(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        from app.infrastructure.models import ProviderUsage

        workflow = await _workflow(uow, owner)
        uow.session.add(
            ProviderUsage(
                workflow_id=workflow.id,
                provider=ProviderName.FAKE,
                service="svc",
                operation="op",
                estimated_cost_minor=10,
                actual_cost_minor=None,
                status=CostStatus.RECONCILED,
            )
        )
        with pytest.raises((IntegrityError, DBAPIError)):
            await uow.session.flush()
        await uow.rollback()

    async def test_budget_comparison(self, uow: UnitOfWork, owner: User) -> None:
        exceeded = await uow.costs.would_exceed_budget(
            current=Money.from_decimal(Decimal("0.85")),
            projected=Money.from_decimal(Decimal("0.20")),
            limit=Money.from_decimal(Decimal("1.00")),
        )
        assert exceeded is True


class TestAuditLog:
    async def test_events_are_recorded_in_order(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        for action in (AuditAction.ENTITY_CREATED, AuditAction.COST_RECORDED):
            await uow.audit.record(
                action=action,
                entity_type="ProductWorkflow",
                entity_id=workflow.id,
                workflow_id=workflow.id,
                summary=f"{action} happened",
            )
        await uow.commit()

        events = await uow.audit.for_workflow(workflow.id)
        assert [event.action for event in events] == [
            AuditAction.ENTITY_CREATED,
            AuditAction.COST_RECORDED,
        ]

    async def test_secrets_are_redacted_before_storage(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        event = await uow.audit.record(
            action=AuditAction.ENTITY_CREATED,
            entity_type="ShopConnection",
            workflow_id=workflow.id,
            summary="Connected",
            after={"api_key": "sk-live-should-never-persist", "shop": "demo"},
            metadata={"nested": {"refresh_token": "rt-secret"}},
        )
        await uow.commit()

        assert event.after is not None
        assert event.after["api_key"] == "[redacted]"
        assert event.after["shop"] == "demo"
        assert event.event_metadata["nested"]["refresh_token"] == "[redacted]"  # type: ignore[index]

    async def test_events_survive_by_entity_lookup(self, uow: UnitOfWork, owner: User) -> None:
        workflow = await _workflow(uow, owner)
        await uow.audit.record(
            action=AuditAction.WORKFLOW_TRANSITION,
            entity_type="ProductWorkflow",
            entity_id=workflow.id,
            workflow_id=workflow.id,
            summary="moved",
        )
        await uow.commit()
        found = await uow.audit.for_entity("ProductWorkflow", workflow.id)
        assert len(found) == 1


class TestDatabaseConstraints:
    async def test_asset_checksum_must_be_sha256_length(self, uow: UnitOfWork, owner: User) -> None:
        from app.infrastructure.models import Asset

        workflow = await _workflow(uow, owner)
        uow.session.add(
            Asset(
                workflow_id=workflow.id,
                storage_key="assets/a.png",
                mime_type="image/png",
                byte_size=100,
                checksum_sha256="tooshort",
            )
        )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()

    async def test_duplicate_asset_checksum_in_one_workflow_is_refused(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        from app.infrastructure.models import Asset

        workflow = await _workflow(uow, owner)
        checksum = "a" * 64
        for index in range(2):
            uow.session.add(
                Asset(
                    workflow_id=workflow.id,
                    storage_key=f"assets/{index}.png",
                    mime_type="image/png",
                    byte_size=100,
                    checksum_sha256=checksum,
                )
            )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()

    async def test_listing_tag_limit_is_enforced_by_the_database(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        from app.infrastructure.models import ListingDraft

        workflow = await _workflow(uow, owner)
        uow.session.add(
            ListingDraft(
                workflow_id=workflow.id,
                title="Title",
                description="Description",
                tags=[f"tag{i}" for i in range(14)],
            )
        )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()

    async def test_duplicate_idempotency_key_is_refused(self, uow: UnitOfWork, owner: User) -> None:
        """A duplicate dispatch must not create a second billable job."""
        from app.infrastructure.models import ArtworkJob, DesignPrompt

        workflow = await _workflow(uow, owner)
        concept = ProductConcept(
            workflow_id=workflow.id,
            title="c",
            description="d",
            origin=ConceptOrigin.MARKET,
            differentiation="x",
        )
        await uow.concepts.add(concept)
        prompt = DesignPrompt(
            concept_id=concept.id, version=1, positive_prompt="p", negative_prompt="n"
        )
        uow.session.add(prompt)
        await uow.session.flush()

        for _ in range(2):
            uow.session.add(
                ArtworkJob(
                    workflow_id=workflow.id,
                    concept_id=concept.id,
                    prompt_id=prompt.id,
                    provider=ProviderName.FAKE,
                    idempotency_key="same-key",
                )
            )
        with pytest.raises(IntegrityError):
            await uow.session.flush()
        await uow.rollback()

    async def test_deleting_a_workflow_cascades_to_its_children(
        self, uow: UnitOfWork, owner: User
    ) -> None:
        workflow = await _workflow(uow, owner)
        await uow.audit.record(
            action=AuditAction.ENTITY_CREATED,
            entity_type="ProductWorkflow",
            workflow_id=workflow.id,
            summary="created",
        )
        await uow.commit()

        await uow.session.execute(
            sqlalchemy.text("DELETE FROM product_workflows WHERE id = :id"),
            {"id": workflow.id},
        )
        await uow.commit()

        remaining = await uow.session.execute(sqlalchemy.text("SELECT count(*) FROM audit_events"))
        assert remaining.scalar_one() == 0

    async def test_enum_rejects_an_unknown_value(self, uow: UnitOfWork, owner: User) -> None:
        """The vocabulary is enforced by PostgreSQL, not only by Python."""
        with pytest.raises(DBAPIError):
            await uow.session.execute(
                sqlalchemy.text(
                    "INSERT INTO product_workflows "
                    "(id, owner_id, idea_mode, name, target_marketplace, "
                    " target_country, output_language, intended_product_uses, "
                    " state, version, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :owner, 'not-a-mode', 'x', 'etsy', "
                    "'US', 'en', '{}', 'DRAFT', 1, now(), now())"
                ),
                {"owner": owner.id},
            )
        await uow.rollback()
