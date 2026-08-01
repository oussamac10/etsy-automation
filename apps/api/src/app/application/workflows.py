"""Workflow use cases.

Each function is one unit of work: it validates against the domain, writes the
entity, records the transition and writes the audit event, then commits.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction, IdeaMode
from app.domain.errors import EntityNotFoundError
from app.domain.ideas import normalize_idea_text, validate_idea_submission
from app.domain.workflow import (
    GATE_SOURCE_STATUS,
    ApprovalDecision,
    ApprovalGate,
    RunStatus,
    apply_approval,
)
from app.infrastructure.models import (
    Approval,
    AuditEvent,
    OriginalIdea,
    ProductWorkflow,
    WorkflowTransition,
)


@dataclass(frozen=True, slots=True)
class CreateWorkflowCommand:
    owner_id: uuid.UUID
    idea_mode: IdeaMode
    name: str
    target_country: str
    output_language: str
    target_marketplace: str = "etsy"
    target_buyer: str | None = None
    intended_product_uses: list[str] = field(default_factory=list)
    actor: str = "owner"


@dataclass(frozen=True, slots=True)
class SubmitIdeaCommand:
    workflow_id: uuid.UUID
    original_text: str
    slogan: str | None = None
    desired_style: str | None = None
    audience: str | None = None
    occasion: str | None = None
    season: str | None = None
    product_uses: list[str] = field(default_factory=list)
    actor: str = "owner"


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """One row of the merged workflow timeline."""

    kind: str
    occurred_at: str
    summary: str
    detail: dict[str, object]


async def create_workflow(uow: UnitOfWork, command: CreateWorkflowCommand) -> ProductWorkflow:
    """Create a workflow in ``DRAFT``.

    Ownership is recorded but not yet *enforced*: Phase 3 adds authentication and
    will reject a request whose caller is not the owner. Until then the owner ID
    is supplied by the caller.
    """
    owner = await uow.users.get(command.owner_id)
    if owner is None:
        raise EntityNotFoundError("User", command.owner_id)

    workflow = ProductWorkflow(
        owner_id=command.owner_id,
        idea_mode=command.idea_mode,
        name=command.name,
        target_marketplace=command.target_marketplace,
        target_country=command.target_country.upper(),
        output_language=command.output_language,
        target_buyer=command.target_buyer,
        intended_product_uses=list(command.intended_product_uses),
        state=RunStatus.DRAFT,
        version=1,
    )
    await uow.workflows.add(workflow)
    await uow.workflows.record_initial_state(workflow, actor=command.actor)
    await uow.audit.record(
        action=AuditAction.ENTITY_CREATED,
        entity_type="ProductWorkflow",
        entity_id=workflow.id,
        workflow_id=workflow.id,
        actor=command.actor,
        summary=f"Workflow created in {command.idea_mode} mode",
        after={"state": RunStatus.DRAFT.value, "idea_mode": command.idea_mode.value},
    )
    await uow.commit()
    return workflow


async def submit_original_idea(uow: UnitOfWork, command: SubmitIdeaCommand) -> OriginalIdea:
    """Store the owner's idea verbatim.

    Refuses a second submission: the first text is the record of what the owner
    said, so a correction is a revision (:func:`revise_original_idea`), never an
    overwrite.
    """
    workflow = await uow.workflows.get(command.workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", command.workflow_id)

    # Raises InvalidIdeaModeError when the mode does not accept an idea, or
    # requires one and got nothing usable.
    validate_idea_submission(workflow.idea_mode, command.original_text)

    existing = await uow.ideas.get_for_workflow(workflow.id)
    if existing is not None:
        from app.domain.errors import ImmutableFieldError

        raise ImmutableFieldError(
            "OriginalIdea",
            "original_text",
            "This workflow already has an original idea; add a revision instead.",
        )

    idea = OriginalIdea(
        workflow_id=workflow.id,
        original_text=command.original_text,
        normalized_text=normalize_idea_text(command.original_text),
        slogan=command.slogan,
        desired_style=command.desired_style,
        audience=command.audience,
        occasion=command.occasion,
        season=command.season,
        product_uses=list(command.product_uses),
    )
    await uow.ideas.add(idea)
    await uow.audit.record(
        action=AuditAction.ENTITY_CREATED,
        entity_type="OriginalIdea",
        entity_id=idea.id,
        workflow_id=workflow.id,
        actor=command.actor,
        summary="Original idea submitted and preserved verbatim",
        # The text itself is not copied into the audit payload: it is already
        # stored, and duplicating user content into the log adds risk for nothing.
        after={"characters": len(command.original_text), "has_slogan": command.slogan is not None},
    )
    await uow.commit()
    return idea


async def revise_original_idea(
    uow: UnitOfWork,
    workflow_id: uuid.UUID,
    *,
    revised_text: str,
    slogan: str | None = None,
    note: str | None = None,
    actor: str = "owner",
) -> object:
    """Append a revision. ``original_text`` is never modified."""
    idea = await uow.ideas.get_for_workflow(workflow_id)
    if idea is None:
        raise EntityNotFoundError("OriginalIdea", workflow_id)

    revision = await uow.ideas.add_revision(
        idea, revised_text=revised_text, slogan=slogan, note=note, actor=actor
    )
    await uow.audit.record(
        action=AuditAction.IDEA_REVISED,
        entity_type="OriginalIdea",
        entity_id=idea.id,
        workflow_id=workflow_id,
        actor=actor,
        summary=f"Idea revised to version {revision.revision_number}",
        after={"revision_number": revision.revision_number},
    )
    await uow.commit()
    return revision


async def transition_workflow(
    uow: UnitOfWork,
    workflow_id: uuid.UUID,
    *,
    to_state: RunStatus,
    expected_version: int,
    reason: str,
    actor: str = "system",
) -> ProductWorkflow:
    """Move a workflow and record the move.

    Raises ``IllegalTransitionError`` for a move the state machine forbids and
    ``ConcurrentModificationError`` when the version has moved on.
    """
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)

    from_state = workflow.state
    transition = await uow.workflows.transition(
        workflow,
        to_state=to_state,
        expected_version=expected_version,
        reason=reason,
        actor=actor,
    )
    await uow.audit.record(
        action=AuditAction.WORKFLOW_TRANSITION,
        entity_type="ProductWorkflow",
        entity_id=workflow.id,
        workflow_id=workflow.id,
        actor=actor,
        summary=f"{from_state} → {to_state} ({reason})",
        before={"state": from_state.value, "version": expected_version},
        after={"state": to_state.value, "version": transition.resulting_version},
    )
    await uow.commit()
    return workflow


async def decide_gate(
    uow: UnitOfWork,
    workflow_id: uuid.UUID,
    *,
    gate: ApprovalGate,
    decision: ApprovalDecision,
    actor: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    target_version: int | None = None,
    comment: str | None = None,
    revision_request: str | None = None,
) -> Approval:
    """Record a human decision at a gate and move the workflow accordingly.

    The decision row and the state change are written in one transaction: an
    approval that did not move the workflow, or a move with no approval behind
    it, would both be lies about what happened.
    """
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)

    previous_state = workflow.state
    # Raises GateNotSatisfiedError when the workflow is not at this gate.
    resulting_state = apply_approval(previous_state, gate, decision=decision)

    approval = await uow.approvals.record(
        workflow=workflow,
        gate=gate,
        decision=decision,
        previous_state=previous_state,
        resulting_state=resulting_state,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        target_version=target_version,
        comment=comment,
        revision_request=revision_request,
    )

    if resulting_state is not previous_state:
        await uow.workflows.transition(
            workflow,
            to_state=resulting_state,
            expected_version=workflow.version,
            reason=f"approval:{gate.value}:{decision.value}",
            actor=actor,
            gate=gate,
            decision=decision,
        )

    await uow.audit.record(
        action=AuditAction.APPROVAL_DECISION,
        entity_type="Approval",
        entity_id=approval.id,
        approval_id=approval.id,
        workflow_id=workflow.id,
        actor=actor,
        summary=f"{gate} decided {decision}",
        before={"state": previous_state.value},
        after={"state": resulting_state.value, "decision": decision.value},
    )
    await uow.commit()
    return approval


async def get_workflow(uow: UnitOfWork, workflow_id: uuid.UUID) -> ProductWorkflow:
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)
    return workflow


async def list_workflows(
    uow: UnitOfWork,
    *,
    owner_id: uuid.UUID | None = None,
    state: RunStatus | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[ProductWorkflow], int]:
    items = await uow.workflows.list(
        owner_id=owner_id,
        state=state,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    total = await uow.workflows.count(
        owner_id=owner_id, state=state, include_archived=include_archived
    )
    return items, total


async def get_timeline(uow: UnitOfWork, workflow_id: uuid.UUID) -> list[TimelineEntry]:
    """Transitions, approvals and audit events merged into one ordered story."""
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)

    transitions: Sequence[WorkflowTransition] = await uow.workflows.transitions(workflow_id)
    approvals: Sequence[Approval] = await uow.approvals.history(workflow_id)
    events: Sequence[AuditEvent] = await uow.audit.for_workflow(workflow_id)

    entries: list[TimelineEntry] = []

    for transition in transitions:
        entries.append(
            TimelineEntry(
                kind="transition",
                occurred_at=transition.created_at.isoformat(),
                summary=(f"{transition.from_state or 'created'} → {transition.to_state}"),
                detail={
                    "from_state": transition.from_state.value if transition.from_state else None,
                    "to_state": transition.to_state.value,
                    "reason": transition.reason,
                    "actor": transition.actor,
                    "version": transition.resulting_version,
                },
            )
        )

    for approval in approvals:
        entries.append(
            TimelineEntry(
                kind="approval",
                occurred_at=(approval.decided_at or approval.created_at).isoformat(),
                summary=f"{approval.gate} — {approval.decision}",
                detail={
                    "gate": approval.gate.value,
                    "decision": approval.decision.value,
                    "actor": approval.actor,
                    "comment": approval.comment,
                    "revision_request": approval.revision_request,
                    "target_type": approval.target_type,
                    "target_version": approval.target_version,
                },
            )
        )

    for event in events:
        # Transitions and approvals are already represented above with more
        # detail; including their audit twins would duplicate every row.
        if event.action in {
            AuditAction.WORKFLOW_TRANSITION,
            AuditAction.APPROVAL_DECISION,
        }:
            continue
        entries.append(
            TimelineEntry(
                kind="audit",
                occurred_at=event.created_at.isoformat(),
                summary=event.summary,
                detail={
                    "action": event.action.value,
                    "entity_type": event.entity_type,
                    "actor": event.actor,
                },
            )
        )

    entries.sort(key=lambda entry: entry.occurred_at)
    return entries


def gate_for_state(state: RunStatus) -> ApprovalGate | None:
    """The gate a workflow is currently sitting at, if any."""
    for gate, source in GATE_SOURCE_STATUS.items():
        if source is state:
            return gate
    return None
