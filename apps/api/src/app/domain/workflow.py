"""The authoritative workflow state machine.

Rules taken directly from the root CLAUDE.md:

* the happy path is a fixed linear sequence;
* failure states are explicit and retryable;
* the three human gates can never be skipped;
* nothing in this module can publish or activate an Etsy listing.

``packages/domain/src/workflow.ts`` mirrors these names for the TypeScript side
and ``apps/api/tests/test_workflow_contract.py`` fails if the two drift.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class RunStatus(StrEnum):
    """Happy-path states, in order."""

    RESEARCHING = "RESEARCHING"
    IDEA_REVIEW = "IDEA_REVIEW"
    ART_GENERATION = "ART_GENERATION"
    ART_REVIEW = "ART_REVIEW"
    PRODUCTION = "PRODUCTION"
    IP_REVIEW = "IP_REVIEW"
    LISTING_REVIEW = "LISTING_REVIEW"
    ETSY_DRAFT_CREATED = "ETSY_DRAFT_CREATED"


class FailureStatus(StrEnum):
    """Explicit failure states. Each one is retryable from its own stage."""

    RESEARCH_FAILED = "RESEARCH_FAILED"
    ART_GENERATION_FAILED = "ART_GENERATION_FAILED"
    PRODUCTION_FAILED = "PRODUCTION_FAILED"
    IP_REVIEW_FAILED = "IP_REVIEW_FAILED"
    ETSY_DRAFT_FAILED = "ETSY_DRAFT_FAILED"


class ApprovalGate(StrEnum):
    """The three mandatory human gates."""

    IDEA_APPROVAL = "IDEA_APPROVAL"
    ARTWORK_APPROVAL = "ARTWORK_APPROVAL"
    LISTING_APPROVAL = "LISTING_APPROVAL"


class RiskLevel(StrEnum):
    """Risk vocabulary. ``safe`` is deliberately not a member."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


RUN_ORDER: tuple[RunStatus, ...] = tuple(RunStatus)

#: Which review state each gate is decided from.
GATE_SOURCE_STATUS: Mapping[ApprovalGate, RunStatus] = MappingProxyType(
    {
        ApprovalGate.IDEA_APPROVAL: RunStatus.IDEA_REVIEW,
        ApprovalGate.ARTWORK_APPROVAL: RunStatus.ART_REVIEW,
        ApprovalGate.LISTING_APPROVAL: RunStatus.LISTING_REVIEW,
    }
)

#: Where an approved gate sends the run next.
GATE_TARGET_STATUS: Mapping[ApprovalGate, RunStatus] = MappingProxyType(
    {
        ApprovalGate.IDEA_APPROVAL: RunStatus.ART_GENERATION,
        ApprovalGate.ARTWORK_APPROVAL: RunStatus.PRODUCTION,
        ApprovalGate.LISTING_APPROVAL: RunStatus.ETSY_DRAFT_CREATED,
    }
)

#: Which failure state each stage falls into, and therefore where a retry resumes.
FAILURE_ORIGIN: Mapping[FailureStatus, RunStatus] = MappingProxyType(
    {
        FailureStatus.RESEARCH_FAILED: RunStatus.RESEARCHING,
        FailureStatus.ART_GENERATION_FAILED: RunStatus.ART_GENERATION,
        FailureStatus.PRODUCTION_FAILED: RunStatus.PRODUCTION,
        FailureStatus.IP_REVIEW_FAILED: RunStatus.IP_REVIEW,
        FailureStatus.ETSY_DRAFT_FAILED: RunStatus.LISTING_REVIEW,
    }
)


def _build_allowed_transitions() -> Mapping[RunStatus, frozenset[RunStatus]]:
    """Linear advance only; no state may skip ahead."""
    transitions: dict[RunStatus, frozenset[RunStatus]] = {}
    for index, status in enumerate(RUN_ORDER):
        nxt = RUN_ORDER[index + 1] if index + 1 < len(RUN_ORDER) else None
        transitions[status] = frozenset() if nxt is None else frozenset({nxt})
    return MappingProxyType(transitions)


ALLOWED_TRANSITIONS = _build_allowed_transitions()

#: States that only a human decision may leave.
GATED_STATUSES: frozenset[RunStatus] = frozenset(GATE_SOURCE_STATUS.values())


class WorkflowError(Exception):
    """Base class for illegal workflow operations."""


class IllegalTransitionError(WorkflowError):
    def __init__(self, current: RunStatus, requested: RunStatus, reason: str) -> None:
        super().__init__(f"Cannot move from {current} to {requested}: {reason}")
        self.current = current
        self.requested = requested
        self.reason = reason


class GateNotSatisfiedError(WorkflowError):
    def __init__(self, gate: ApprovalGate, current: RunStatus) -> None:
        super().__init__(
            f"Gate {gate} cannot be decided while the run is in {current}; "
            f"it requires {GATE_SOURCE_STATUS[gate]}."
        )
        self.gate = gate
        self.current = current


def can_transition(current: RunStatus, requested: RunStatus) -> bool:
    """True when ``requested`` is the immediate successor of ``current``."""
    return requested in ALLOWED_TRANSITIONS[current]


def advance(current: RunStatus, requested: RunStatus) -> RunStatus:
    """Move the run forward one state.

    Leaving a gated state requires :func:`apply_approval`; this function refuses
    it so no code path can bypass a human decision by advancing directly.
    """
    if current in GATED_STATUSES:
        raise IllegalTransitionError(
            current,
            requested,
            "this state is a human approval gate; use apply_approval()",
        )
    if not can_transition(current, requested):
        raise IllegalTransitionError(current, requested, "not the next state in the workflow")
    return requested


def apply_approval(current: RunStatus, gate: ApprovalGate, *, approved: bool) -> RunStatus:
    """Record a human decision at ``gate``.

    An approval advances the run. A rejection leaves it in the review state so
    the owner can iterate — a rejected idea never reaches artwork generation.
    """
    if current is not GATE_SOURCE_STATUS[gate]:
        raise GateNotSatisfiedError(gate, current)
    return GATE_TARGET_STATUS[gate] if approved else current


def fail(current: RunStatus, failure: FailureStatus) -> FailureStatus:
    """Move a running stage into its explicit failure state."""
    if FAILURE_ORIGIN[failure] is not current:
        raise IllegalTransitionError(
            current,
            FAILURE_ORIGIN[failure],
            f"{failure} can only be raised from {FAILURE_ORIGIN[failure]}",
        )
    return failure


def retry(failure: FailureStatus) -> RunStatus:
    """Return the state a failed run resumes from. Every failure is retryable."""
    return FAILURE_ORIGIN[failure]


def is_terminal_success(status: RunStatus) -> bool:
    """The workflow ends at a *draft*. There is no published state, by design."""
    return status is RunStatus.ETSY_DRAFT_CREATED
