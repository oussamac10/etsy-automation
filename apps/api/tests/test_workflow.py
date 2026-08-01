"""Workflow state machine.

Phase 1 established the three gates and the retryable failure model. Phase 2
extended the pipeline to fifteen states with an explicit transition table, so
the "strictly linear successor" assertions became "the table says what it says".
Every Phase 1 guarantee is still asserted below.
"""

from __future__ import annotations

import pytest

from app.domain.workflow import (
    ALLOWED_TRANSITIONS,
    GATE_PREREQUISITE,
    GATE_REJECTION_STATUS,
    GATE_REVISION_STATUS,
    GATE_SOURCE_STATUS,
    GATE_TARGET_STATUS,
    GATED_STATUSES,
    HAPPY_PATH,
    TERMINAL_STATUSES,
    ApprovalDecision,
    ApprovalGate,
    FailureStatus,
    GateNotApprovedError,
    GateNotSatisfiedError,
    IllegalTransitionError,
    RiskLevel,
    RunStatus,
    advance,
    apply_approval,
    can_transition,
    fail,
    is_terminal_success,
    require_artwork_approved,
    require_idea_approved,
    require_listing_approved,
    retry,
)


class TestStates:
    def test_happy_path_is_declared_in_order(self) -> None:
        assert [status.value for status in HAPPY_PATH] == [
            "DRAFT",
            "RESEARCH_QUEUED",
            "RESEARCHING",
            "IDEA_REVIEW",
            "IDEA_APPROVED",
            "ART_QUEUED",
            "ART_GENERATION",
            "ART_REVIEW",
            "ARTWORK_APPROVED",
            "PRODUCTION",
            "IP_REVIEW",
            "LISTING_REVIEW",
            "READY_FOR_ETSY_DRAFT",
            "ETSY_DRAFT_CREATED",
        ]

    def test_every_state_is_reachable_or_terminal(self) -> None:
        """No state may be declared and then orphaned."""
        reachable = {RunStatus.DRAFT}
        for targets in ALLOWED_TRANSITIONS.values():
            reachable |= targets
        assert reachable == set(RunStatus)

    def test_phase_1_state_names_are_preserved(self) -> None:
        """Extending the machine must not rename what Phase 1 established."""
        names = {status.value for status in RunStatus}
        for name in (
            "RESEARCHING",
            "IDEA_REVIEW",
            "ART_GENERATION",
            "ART_REVIEW",
            "PRODUCTION",
            "IP_REVIEW",
            "LISTING_REVIEW",
            "ETSY_DRAFT_CREATED",
        ):
            assert name in names

    def test_terminal_states_have_no_exit(self) -> None:
        for status in TERMINAL_STATUSES:
            assert ALLOWED_TRANSITIONS[status] == frozenset()

    def test_draft_creation_is_the_only_terminal_success(self) -> None:
        assert is_terminal_success(RunStatus.ETSY_DRAFT_CREATED)
        assert not is_terminal_success(RunStatus.PUBLISHED)
        assert not is_terminal_success(RunStatus.LISTING_REVIEW)


class TestTransitions:
    @pytest.mark.parametrize(
        ("current", "expected"),
        [(HAPPY_PATH[i], HAPPY_PATH[i + 1]) for i in range(len(HAPPY_PATH) - 1)],
    )
    def test_each_happy_path_step_is_allowed(self, current: RunStatus, expected: RunStatus) -> None:
        assert can_transition(current, expected)

    def test_advance_moves_a_non_gated_state(self) -> None:
        assert advance(RunStatus.DRAFT, RunStatus.RESEARCH_QUEUED) is RunStatus.RESEARCH_QUEUED

    def test_cannot_skip_a_state(self) -> None:
        with pytest.raises(IllegalTransitionError):
            advance(RunStatus.ART_GENERATION, RunStatus.PRODUCTION)

    def test_cannot_move_backwards_arbitrarily(self) -> None:
        with pytest.raises(IllegalTransitionError):
            advance(RunStatus.PRODUCTION, RunStatus.ART_GENERATION)

    def test_cannot_leave_a_terminal_state(self) -> None:
        with pytest.raises(IllegalTransitionError, match="terminal"):
            advance(RunStatus.PUBLISHED, RunStatus.LISTING_REVIEW)
        with pytest.raises(IllegalTransitionError, match="terminal"):
            advance(RunStatus.CANCELLED, RunStatus.DRAFT)

    @pytest.mark.parametrize("gated", sorted(GATED_STATUSES))
    def test_a_gated_state_cannot_be_advanced_directly(self, gated: RunStatus) -> None:
        """The three human gates must not be bypassable by a state change."""
        index = HAPPY_PATH.index(gated)
        with pytest.raises(IllegalTransitionError, match="human approval gate"):
            advance(gated, HAPPY_PATH[index + 1])

    def test_queued_work_can_be_withdrawn(self) -> None:
        assert advance(RunStatus.RESEARCH_QUEUED, RunStatus.DRAFT) is RunStatus.DRAFT
        assert advance(RunStatus.ART_QUEUED, RunStatus.IDEA_APPROVED) is RunStatus.IDEA_APPROVED

    @pytest.mark.parametrize("state", [s for s in RunStatus if s not in TERMINAL_STATUSES])
    def test_any_live_workflow_can_be_cancelled(self, state: RunStatus) -> None:
        assert advance(state, RunStatus.CANCELLED) is RunStatus.CANCELLED


class TestPublicationIsHumanOnly:
    """The application creates drafts. A person publishes."""

    def test_published_is_reachable_only_from_a_created_draft(self) -> None:
        sources = [
            state
            for state, targets in ALLOWED_TRANSITIONS.items()
            if RunStatus.PUBLISHED in targets
        ]
        assert sources == [RunStatus.ETSY_DRAFT_CREATED]

    def test_no_gate_target_is_published(self) -> None:
        """No approval can put a workflow straight into PUBLISHED."""
        assert RunStatus.PUBLISHED not in set(GATE_TARGET_STATUS.values())

    def test_publication_requires_the_final_gate(self) -> None:
        """A workflow cannot reach a draft, let alone publication, before gate 3."""
        for state in (
            RunStatus.DRAFT,
            RunStatus.IDEA_REVIEW,
            RunStatus.ART_REVIEW,
            RunStatus.PRODUCTION,
            RunStatus.IP_REVIEW,
            RunStatus.LISTING_REVIEW,
        ):
            with pytest.raises(GateNotApprovedError):
                require_listing_approved(state)


class TestGates:
    def test_there_are_exactly_three_gates(self) -> None:
        assert len(list(ApprovalGate)) == 3

    @pytest.mark.parametrize(
        ("gate", "source", "target"),
        [
            (ApprovalGate.IDEA_APPROVAL, RunStatus.IDEA_REVIEW, RunStatus.IDEA_APPROVED),
            (
                ApprovalGate.ARTWORK_APPROVAL,
                RunStatus.ART_REVIEW,
                RunStatus.ARTWORK_APPROVED,
            ),
            (
                ApprovalGate.LISTING_APPROVAL,
                RunStatus.LISTING_REVIEW,
                RunStatus.READY_FOR_ETSY_DRAFT,
            ),
        ],
    )
    def test_approval_advances_the_workflow(
        self, gate: ApprovalGate, source: RunStatus, target: RunStatus
    ) -> None:
        assert apply_approval(source, gate, decision=ApprovalDecision.APPROVED) is target

    @pytest.mark.parametrize("gate", list(ApprovalGate))
    def test_rejection_returns_to_the_producing_stage(self, gate: ApprovalGate) -> None:
        source = GATE_SOURCE_STATUS[gate]
        result = apply_approval(source, gate, decision=ApprovalDecision.REJECTED)
        assert result is GATE_REJECTION_STATUS[gate]
        # A rejection must never advance the workflow.
        assert HAPPY_PATH.index(result) < HAPPY_PATH.index(source)

    @pytest.mark.parametrize("gate", list(ApprovalGate))
    def test_revision_request_returns_to_a_producing_state(self, gate: ApprovalGate) -> None:
        source = GATE_SOURCE_STATUS[gate]
        result = apply_approval(source, gate, decision=ApprovalDecision.REVISION_REQUESTED)
        assert result is GATE_REVISION_STATUS[gate]
        assert HAPPY_PATH.index(result) < HAPPY_PATH.index(source)

    def test_pending_is_not_a_decision(self) -> None:
        with pytest.raises(IllegalTransitionError, match="PENDING"):
            apply_approval(
                RunStatus.IDEA_REVIEW,
                ApprovalGate.IDEA_APPROVAL,
                decision=ApprovalDecision.PENDING,
            )

    def test_gate_cannot_be_decided_from_the_wrong_state(self) -> None:
        with pytest.raises(GateNotSatisfiedError):
            apply_approval(
                RunStatus.DRAFT,
                ApprovalGate.IDEA_APPROVAL,
                decision=ApprovalDecision.APPROVED,
            )

    def test_listing_gate_cannot_be_used_to_skip_ip_review(self) -> None:
        with pytest.raises(GateNotSatisfiedError):
            apply_approval(
                RunStatus.IP_REVIEW,
                ApprovalGate.LISTING_APPROVAL,
                decision=ApprovalDecision.APPROVED,
            )

    def test_rejected_idea_cannot_reach_artwork_generation(self) -> None:
        state = apply_approval(
            RunStatus.IDEA_REVIEW,
            ApprovalGate.IDEA_APPROVAL,
            decision=ApprovalDecision.REJECTED,
        )
        with pytest.raises(GateNotApprovedError):
            require_idea_approved(state)


class TestStageGuards:
    """Artwork needs gate 1, production needs gate 2, drafts need gate 3."""

    @pytest.mark.parametrize(
        "blocked_state",
        [
            RunStatus.DRAFT,
            RunStatus.RESEARCH_QUEUED,
            RunStatus.RESEARCHING,
            RunStatus.IDEA_REVIEW,
        ],
    )
    def test_artwork_blocked_before_idea_approval(self, blocked_state: RunStatus) -> None:
        with pytest.raises(GateNotApprovedError, match="Artwork generation"):
            require_idea_approved(blocked_state)

    def test_artwork_allowed_once_idea_is_approved(self) -> None:
        require_idea_approved(RunStatus.IDEA_APPROVED)
        require_idea_approved(RunStatus.ART_GENERATION)

    @pytest.mark.parametrize(
        "blocked_state",
        [
            RunStatus.IDEA_APPROVED,
            RunStatus.ART_QUEUED,
            RunStatus.ART_GENERATION,
            RunStatus.ART_REVIEW,
        ],
    )
    def test_production_blocked_before_artwork_approval(self, blocked_state: RunStatus) -> None:
        with pytest.raises(GateNotApprovedError, match="Production"):
            require_artwork_approved(blocked_state)

    def test_production_allowed_once_artwork_is_approved(self) -> None:
        require_artwork_approved(RunStatus.ARTWORK_APPROVED)
        require_artwork_approved(RunStatus.PRODUCTION)

    def test_draft_creation_allowed_once_listing_is_approved(self) -> None:
        require_listing_approved(RunStatus.READY_FOR_ETSY_DRAFT)
        require_listing_approved(RunStatus.ETSY_DRAFT_CREATED)

    def test_guards_reject_a_cancelled_workflow(self) -> None:
        for guard in (
            require_idea_approved,
            require_artwork_approved,
            require_listing_approved,
        ):
            with pytest.raises(GateNotApprovedError):
                guard(RunStatus.CANCELLED)

    def test_every_gate_prerequisite_is_its_approval_target(self) -> None:
        assert GATE_PREREQUISITE == GATE_TARGET_STATUS


class TestFailureAndRetry:
    @pytest.mark.parametrize(
        ("origin", "failure"),
        [
            (RunStatus.RESEARCHING, FailureStatus.RESEARCH_FAILED),
            (RunStatus.ART_GENERATION, FailureStatus.ART_GENERATION_FAILED),
            (RunStatus.PRODUCTION, FailureStatus.PRODUCTION_FAILED),
            (RunStatus.IP_REVIEW, FailureStatus.IP_REVIEW_FAILED),
            (RunStatus.READY_FOR_ETSY_DRAFT, FailureStatus.ETSY_DRAFT_FAILED),
        ],
    )
    def test_every_failure_is_retryable_from_its_origin(
        self, origin: RunStatus, failure: FailureStatus
    ) -> None:
        assert fail(origin, failure) is failure
        assert retry(failure) is origin

    def test_failure_cannot_be_raised_from_an_unrelated_state(self) -> None:
        with pytest.raises(IllegalTransitionError):
            fail(RunStatus.RESEARCHING, FailureStatus.PRODUCTION_FAILED)


class TestRisk:
    def test_safe_is_not_a_risk_level(self) -> None:
        assert "safe" not in {level.value for level in RiskLevel}

    def test_risk_levels_are_exactly_the_four_allowed(self) -> None:
        assert {level.value for level in RiskLevel} == {
            "low",
            "medium",
            "high",
            "unknown",
        }
