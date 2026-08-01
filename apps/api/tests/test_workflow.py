from __future__ import annotations

import pytest

from app.domain.workflow import (
    GATED_STATUSES,
    RUN_ORDER,
    ApprovalGate,
    FailureStatus,
    GateNotSatisfiedError,
    IllegalTransitionError,
    RiskLevel,
    RunStatus,
    advance,
    apply_approval,
    can_transition,
    fail,
    is_terminal_success,
    retry,
)


class TestOrdering:
    def test_states_are_declared_in_workflow_order(self) -> None:
        assert [status.value for status in RUN_ORDER] == [
            "RESEARCHING",
            "IDEA_REVIEW",
            "ART_GENERATION",
            "ART_REVIEW",
            "PRODUCTION",
            "IP_REVIEW",
            "LISTING_REVIEW",
            "ETSY_DRAFT_CREATED",
        ]

    def test_only_the_immediate_successor_is_allowed(self) -> None:
        assert can_transition(RunStatus.RESEARCHING, RunStatus.IDEA_REVIEW)
        assert not can_transition(RunStatus.RESEARCHING, RunStatus.ART_GENERATION)

    def test_terminal_state_has_no_successor(self) -> None:
        assert not can_transition(RunStatus.ETSY_DRAFT_CREATED, RunStatus.ETSY_DRAFT_CREATED)
        assert is_terminal_success(RunStatus.ETSY_DRAFT_CREATED)

    def test_no_published_or_active_state_exists(self) -> None:
        names = {status.value for status in RunStatus}
        assert not names & {"PUBLISHED", "ACTIVE", "LIVE"}


class TestAdvance:
    def test_advances_a_non_gated_state(self) -> None:
        assert advance(RunStatus.RESEARCHING, RunStatus.IDEA_REVIEW) is RunStatus.IDEA_REVIEW

    def test_cannot_skip_a_state(self) -> None:
        with pytest.raises(IllegalTransitionError):
            advance(RunStatus.ART_GENERATION, RunStatus.PRODUCTION)

    def test_cannot_move_backwards(self) -> None:
        with pytest.raises(IllegalTransitionError):
            advance(RunStatus.PRODUCTION, RunStatus.ART_GENERATION)

    @pytest.mark.parametrize("gated", sorted(GATED_STATUSES))
    def test_a_gated_state_cannot_be_advanced_directly(self, gated: RunStatus) -> None:
        """The three human gates must not be bypassable by a state change."""
        index = RUN_ORDER.index(gated)
        with pytest.raises(IllegalTransitionError, match="human approval gate"):
            advance(gated, RUN_ORDER[index + 1])


class TestGates:
    def test_there_are_exactly_three_gates(self) -> None:
        assert len(list(ApprovalGate)) == 3

    @pytest.mark.parametrize(
        ("gate", "source", "target"),
        [
            (ApprovalGate.IDEA_APPROVAL, RunStatus.IDEA_REVIEW, RunStatus.ART_GENERATION),
            (ApprovalGate.ARTWORK_APPROVAL, RunStatus.ART_REVIEW, RunStatus.PRODUCTION),
            (
                ApprovalGate.LISTING_APPROVAL,
                RunStatus.LISTING_REVIEW,
                RunStatus.ETSY_DRAFT_CREATED,
            ),
        ],
    )
    def test_approval_advances_the_run(
        self, gate: ApprovalGate, source: RunStatus, target: RunStatus
    ) -> None:
        assert apply_approval(source, gate, approved=True) is target

    def test_rejection_keeps_the_run_in_review(self) -> None:
        assert (
            apply_approval(RunStatus.IDEA_REVIEW, ApprovalGate.IDEA_APPROVAL, approved=False)
            is RunStatus.IDEA_REVIEW
        )

    def test_rejected_idea_cannot_reach_artwork_generation(self) -> None:
        state = apply_approval(RunStatus.IDEA_REVIEW, ApprovalGate.IDEA_APPROVAL, approved=False)
        assert state is not RunStatus.ART_GENERATION
        with pytest.raises(IllegalTransitionError):
            advance(state, RunStatus.ART_GENERATION)

    def test_gate_cannot_be_decided_from_the_wrong_state(self) -> None:
        with pytest.raises(GateNotSatisfiedError):
            apply_approval(RunStatus.RESEARCHING, ApprovalGate.IDEA_APPROVAL, approved=True)

    def test_listing_gate_cannot_be_used_to_skip_ip_review(self) -> None:
        with pytest.raises(GateNotSatisfiedError):
            apply_approval(RunStatus.IP_REVIEW, ApprovalGate.LISTING_APPROVAL, approved=True)


class TestFailureAndRetry:
    @pytest.mark.parametrize(
        ("origin", "failure"),
        [
            (RunStatus.RESEARCHING, FailureStatus.RESEARCH_FAILED),
            (RunStatus.ART_GENERATION, FailureStatus.ART_GENERATION_FAILED),
            (RunStatus.PRODUCTION, FailureStatus.PRODUCTION_FAILED),
            (RunStatus.IP_REVIEW, FailureStatus.IP_REVIEW_FAILED),
            (RunStatus.LISTING_REVIEW, FailureStatus.ETSY_DRAFT_FAILED),
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
        assert {level.value for level in RiskLevel} == {"low", "medium", "high", "unknown"}
