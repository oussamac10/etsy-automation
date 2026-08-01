"""The authoritative workflow state machine.

Rules taken directly from the root CLAUDE.md:

* the happy path is a fixed sequence;
* failure states are explicit and retryable;
* the three human gates can never be skipped;
* nothing in this module can publish or activate an Etsy listing.

``packages/domain/src/workflow.ts`` mirrors these names for the TypeScript side
and ``apps/api/tests/test_workflow_contract.py`` fails if the two drift.

Phase 2 extended the Phase 1 pipeline from eight states to fifteen. Every Phase 1
name is preserved with its original meaning; the new states name moments that
Phase 1 collapsed together — a workflow before research starts (``DRAFT``), work
that is queued but not yet running, and the settled results of the two artwork
gates. See ``docs/workflow-state-machine.md`` for the complete transition table.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from app.domain.errors import DomainError


class RunStatus(StrEnum):
    """Workflow states.

    Ordered along the happy path, then the two terminal-ish states that leave it
    (``PUBLISHED`` is recorded by a human, ``CANCELLED`` ends the workflow).
    """

    #: Created, brief captured, nothing dispatched yet.
    DRAFT = "DRAFT"
    #: A research job is enqueued but has not started.
    RESEARCH_QUEUED = "RESEARCH_QUEUED"
    #: Research is running.
    RESEARCHING = "RESEARCHING"
    #: Ranked concepts are waiting for human gate 1.
    IDEA_REVIEW = "IDEA_REVIEW"
    #: Gate 1 approved. The chosen concept and prompt version are frozen.
    IDEA_APPROVED = "IDEA_APPROVED"
    #: An artwork job is enqueued but has not started.
    ART_QUEUED = "ART_QUEUED"
    #: Artwork generation is running.
    ART_GENERATION = "ART_GENERATION"
    #: Alternatives are waiting for human gate 2.
    ART_REVIEW = "ART_REVIEW"
    #: Gate 2 approved. The chosen asset is frozen.
    ARTWORK_APPROVED = "ARTWORK_APPROVED"
    #: Asset production: background, trim, typography, upscale, mockups, QA.
    PRODUCTION = "PRODUCTION"
    #: Preliminary phrase and IP risk review.
    IP_REVIEW = "IP_REVIEW"
    #: Listing copy, package and IP acknowledgement waiting for human gate 3.
    LISTING_REVIEW = "LISTING_REVIEW"
    #: Gate 3 approved. Everything needed to create the draft is validated.
    READY_FOR_ETSY_DRAFT = "READY_FOR_ETSY_DRAFT"
    #: A draft exists in Etsy. The workflow's automated work ends here.
    ETSY_DRAFT_CREATED = "ETSY_DRAFT_CREATED"
    #: The owner published the draft *themselves* and told us. See below.
    PUBLISHED = "PUBLISHED"
    #: Abandoned by the owner. Terminal.
    CANCELLED = "CANCELLED"


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


class ApprovalDecision(StrEnum):
    """A gate decision. ``PENDING`` is the state of an unanswered request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


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

#: The happy path, in order. Excludes PUBLISHED and CANCELLED, which leave it.
HAPPY_PATH: tuple[RunStatus, ...] = (
    RunStatus.DRAFT,
    RunStatus.RESEARCH_QUEUED,
    RunStatus.RESEARCHING,
    RunStatus.IDEA_REVIEW,
    RunStatus.IDEA_APPROVED,
    RunStatus.ART_QUEUED,
    RunStatus.ART_GENERATION,
    RunStatus.ART_REVIEW,
    RunStatus.ARTWORK_APPROVED,
    RunStatus.PRODUCTION,
    RunStatus.IP_REVIEW,
    RunStatus.LISTING_REVIEW,
    RunStatus.READY_FOR_ETSY_DRAFT,
    RunStatus.ETSY_DRAFT_CREATED,
)

#: Terminal states: nothing may leave them.
TERMINAL_STATUSES: frozenset[RunStatus] = frozenset({RunStatus.PUBLISHED, RunStatus.CANCELLED})

#: Which review state each gate is decided from.
GATE_SOURCE_STATUS: Mapping[ApprovalGate, RunStatus] = MappingProxyType(
    {
        ApprovalGate.IDEA_APPROVAL: RunStatus.IDEA_REVIEW,
        ApprovalGate.ARTWORK_APPROVAL: RunStatus.ART_REVIEW,
        ApprovalGate.LISTING_APPROVAL: RunStatus.LISTING_REVIEW,
    }
)

#: Where an approved gate sends the workflow next.
GATE_TARGET_STATUS: Mapping[ApprovalGate, RunStatus] = MappingProxyType(
    {
        ApprovalGate.IDEA_APPROVAL: RunStatus.IDEA_APPROVED,
        ApprovalGate.ARTWORK_APPROVAL: RunStatus.ARTWORK_APPROVED,
        ApprovalGate.LISTING_APPROVAL: RunStatus.READY_FOR_ETSY_DRAFT,
    }
)

#: Where a rejection sends the workflow. A rejection is not a failure: it returns
#: the workflow to the stage that produced the rejected artefact so it can be
#: redone, and no paid child job is dispatched in the meantime.
GATE_REJECTION_STATUS: Mapping[ApprovalGate, RunStatus] = MappingProxyType(
    {
        # A rejected set of concepts means the research itself must be redone.
        ApprovalGate.IDEA_APPROVAL: RunStatus.DRAFT,
        # Rejected artwork goes back to generation, not back to the idea gate.
        ApprovalGate.ARTWORK_APPROVAL: RunStatus.IDEA_APPROVED,
        # A rejected listing goes back to production; the artwork stays approved.
        ApprovalGate.LISTING_APPROVAL: RunStatus.ARTWORK_APPROVED,
    }
)

#: Where a revision request sends the workflow. Unlike a rejection, the reviewer
#: wants the same artefact changed rather than replaced, so it returns to the
#: nearest state that can produce a new version.
GATE_REVISION_STATUS: Mapping[ApprovalGate, RunStatus] = MappingProxyType(
    {
        ApprovalGate.IDEA_APPROVAL: RunStatus.RESEARCH_QUEUED,
        ApprovalGate.ARTWORK_APPROVAL: RunStatus.ART_QUEUED,
        ApprovalGate.LISTING_APPROVAL: RunStatus.PRODUCTION,
    }
)

#: Which failure state each stage falls into, and therefore where a retry resumes.
FAILURE_ORIGIN: Mapping[FailureStatus, RunStatus] = MappingProxyType(
    {
        FailureStatus.RESEARCH_FAILED: RunStatus.RESEARCHING,
        FailureStatus.ART_GENERATION_FAILED: RunStatus.ART_GENERATION,
        FailureStatus.PRODUCTION_FAILED: RunStatus.PRODUCTION,
        FailureStatus.IP_REVIEW_FAILED: RunStatus.IP_REVIEW,
        FailureStatus.ETSY_DRAFT_FAILED: RunStatus.READY_FOR_ETSY_DRAFT,
    }
)


def _build_allowed_transitions() -> Mapping[RunStatus, frozenset[RunStatus]]:
    """The complete transition table.

    The happy path advances one state at a time. On top of that:

    * every non-terminal state may be cancelled;
    * a queued state may return to its predecessor if the job is withdrawn
      before it runs;
    * gate outcomes are **not** listed here — leaving a review state requires
      :func:`apply_approval`, so no caller can bypass a human decision by
      requesting a transition.
    """
    transitions: dict[RunStatus, set[RunStatus]] = {status: set() for status in RunStatus}

    for index, status in enumerate(HAPPY_PATH[:-1]):
        transitions[status].add(HAPPY_PATH[index + 1])

    # Withdrawing queued work before it starts.
    transitions[RunStatus.RESEARCH_QUEUED].add(RunStatus.DRAFT)
    transitions[RunStatus.ART_QUEUED].add(RunStatus.IDEA_APPROVED)

    # Publication is a human action performed in Etsy. The application records
    # it after the fact; it never performs it. Only ETSY_DRAFT_CREATED may lead
    # here, so a workflow can never be marked published without a draft.
    transitions[RunStatus.ETSY_DRAFT_CREATED].add(RunStatus.PUBLISHED)

    for status in RunStatus:
        if status not in TERMINAL_STATUSES:
            transitions[status].add(RunStatus.CANCELLED)

    return MappingProxyType({status: frozenset(targets) for status, targets in transitions.items()})


ALLOWED_TRANSITIONS = _build_allowed_transitions()

#: States that only a human decision may leave.
GATED_STATUSES: frozenset[RunStatus] = frozenset(GATE_SOURCE_STATUS.values())

#: The state each gate must have reached before the *next* stage may run. Used by
#: the guards below so "artwork needs idea approval" is data, not scattered ifs.
GATE_PREREQUISITE: Mapping[ApprovalGate, RunStatus] = MappingProxyType(
    {
        ApprovalGate.IDEA_APPROVAL: RunStatus.IDEA_APPROVED,
        ApprovalGate.ARTWORK_APPROVAL: RunStatus.ARTWORK_APPROVED,
        ApprovalGate.LISTING_APPROVAL: RunStatus.READY_FOR_ETSY_DRAFT,
    }
)


class WorkflowError(DomainError):
    """Base class for illegal workflow operations.

    A subclass of :class:`~app.domain.errors.DomainError` so the HTTP layer maps
    it to a problem document like every other rule, rather than letting it fall
    through to the generic 500 handler.
    """


class IllegalTransitionError(WorkflowError):
    def __init__(self, current: RunStatus, requested: RunStatus, reason: str) -> None:
        super().__init__(f"Cannot move from {current} to {requested}: {reason}")
        self.current = current
        self.requested = requested
        self.reason = reason


class GateNotSatisfiedError(WorkflowError):
    def __init__(self, gate: ApprovalGate, current: RunStatus) -> None:
        super().__init__(
            f"Gate {gate} cannot be decided while the workflow is in {current}; "
            f"it requires {GATE_SOURCE_STATUS[gate]}."
        )
        self.gate = gate
        self.current = current


class GateNotApprovedError(WorkflowError):
    """A stage was attempted before the gate that guards it was approved."""

    def __init__(self, gate: ApprovalGate, current: RunStatus, action: str) -> None:
        super().__init__(
            f"{action} requires gate {gate} to be approved; the workflow is in {current}."
        )
        self.gate = gate
        self.current = current
        self.action = action


def can_transition(current: RunStatus, requested: RunStatus) -> bool:
    """True when ``requested`` is reachable from ``current`` in one step."""
    return requested in ALLOWED_TRANSITIONS[current]


def advance(current: RunStatus, requested: RunStatus) -> RunStatus:
    """Move the workflow to ``requested``.

    Leaving a gated state requires :func:`apply_approval`; this function refuses
    it so no code path can bypass a human decision by advancing directly.
    """
    if current in TERMINAL_STATUSES:
        raise IllegalTransitionError(current, requested, f"{current} is terminal")
    if current in GATED_STATUSES and requested is not RunStatus.CANCELLED:
        raise IllegalTransitionError(
            current,
            requested,
            "this state is a human approval gate; use apply_approval()",
        )
    if not can_transition(current, requested):
        raise IllegalTransitionError(current, requested, "not a permitted transition")
    return requested


def apply_approval(
    current: RunStatus,
    gate: ApprovalGate,
    *,
    decision: ApprovalDecision,
) -> RunStatus:
    """Record a human decision at ``gate`` and return the resulting state.

    ``APPROVED`` advances. ``REJECTED`` sends the workflow back to the stage that
    produced the rejected artefact. ``REVISION_REQUESTED`` sends it back to the
    nearest state that can produce a new version. ``PENDING`` is not a decision
    and is refused.
    """
    if current is not GATE_SOURCE_STATUS[gate]:
        raise GateNotSatisfiedError(gate, current)

    match decision:
        case ApprovalDecision.APPROVED:
            return GATE_TARGET_STATUS[gate]
        case ApprovalDecision.REJECTED:
            return GATE_REJECTION_STATUS[gate]
        case ApprovalDecision.REVISION_REQUESTED:
            return GATE_REVISION_STATUS[gate]
        case ApprovalDecision.PENDING:
            raise IllegalTransitionError(current, current, "PENDING is not a decision")


def require_gate(current: RunStatus, gate: ApprovalGate, action: str) -> None:
    """Guard a stage behind its gate.

    Raises :class:`GateNotApprovedError` unless the workflow has reached — or
    passed — the state that gate's approval produces. This is what makes
    "artwork generation is impossible without idea approval" enforceable from
    anywhere, not just from the transition table.
    """
    prerequisite = GATE_PREREQUISITE[gate]
    if current in TERMINAL_STATUSES or current not in HAPPY_PATH:
        raise GateNotApprovedError(gate, current, action)
    if HAPPY_PATH.index(current) < HAPPY_PATH.index(prerequisite):
        raise GateNotApprovedError(gate, current, action)


def require_idea_approved(current: RunStatus) -> None:
    """Artwork generation is impossible without gate 1."""
    require_gate(current, ApprovalGate.IDEA_APPROVAL, "Artwork generation")


def require_artwork_approved(current: RunStatus) -> None:
    """Production is impossible without gate 2."""
    require_gate(current, ApprovalGate.ARTWORK_APPROVAL, "Production")


def require_listing_approved(current: RunStatus) -> None:
    """Draft creation and publication are impossible without gate 3."""
    require_gate(current, ApprovalGate.LISTING_APPROVAL, "Etsy draft creation")


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
    """Return the state a failed workflow resumes from. Every failure is retryable."""
    return FAILURE_ORIGIN[failure]


def is_terminal_success(status: RunStatus) -> bool:
    """The application's own work ends at a *draft*.

    ``PUBLISHED`` exists only as a record that the owner published the draft in
    Etsy themselves. There is no code path that publishes, and ``EtsyGateway``
    has no publish method.
    """
    return status is RunStatus.ETSY_DRAFT_CREATED
