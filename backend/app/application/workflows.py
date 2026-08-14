"""Workflow use cases.

Each function is one unit of work: it validates against the domain, writes the
entity, records the transition and writes the audit event, then commits.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.application.research import queue_research_run
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction, ConceptStatus, IdeaMode
from app.domain.errors import (
    ConcurrentModificationError,
    EntityNotFoundError,
    UnresolvedRiskError,
)
from app.domain.ideas import normalize_idea_text, validate_idea_submission
from app.domain.workflow import (
    GATE_SOURCE_STATUS,
    IN_FLIGHT_STATUSES,
    ApprovalDecision,
    ApprovalGate,
    IllegalTransitionError,
    RiskLevel,
    RunStatus,
    apply_approval,
)
from app.infrastructure.models import (
    Approval,
    Asset,
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
    #: From the session, not the request body.
    owner_id: uuid.UUID
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


async def _owned_workflow(
    uow: UnitOfWork, workflow_id: uuid.UUID, owner_id: uuid.UUID
) -> ProductWorkflow:
    """Load a workflow that belongs to ``owner_id``, or raise 404.

    A workflow owned by someone else raises the *same* ``EntityNotFoundError``
    as one that does not exist. A 403 would confirm the ID is real, which is
    existence information the caller is not entitled to. Documented in
    ``docs/authentication-and-secrets.md``.

    Every read and every mutation goes through here, so ownership is one
    function rather than a rule each use case has to remember.
    """
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None or workflow.owner_id != owner_id:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)
    return workflow


async def create_workflow(uow: UnitOfWork, command: CreateWorkflowCommand) -> ProductWorkflow:
    """Create a workflow in ``DRAFT``.

    ``command.owner_id`` comes from the authenticated session, never from the
    request body: the route builds this command from the resolved identity.
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
    workflow = await _owned_workflow(uow, command.workflow_id, command.owner_id)

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
    owner_id: uuid.UUID,
    revised_text: str,
    slogan: str | None = None,
    note: str | None = None,
    actor: str = "owner",
) -> object:
    """Append a revision. ``original_text`` is never modified."""
    await _owned_workflow(uow, workflow_id, owner_id)
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
    owner_id: uuid.UUID,
    to_state: RunStatus,
    expected_version: int,
    reason: str,
    actor: str = "system",
) -> ProductWorkflow:
    """Move a workflow and record the move.

    Raises ``IllegalTransitionError`` for a move the state machine forbids and
    ``ConcurrentModificationError`` when the version has moved on.
    """
    workflow = await _owned_workflow(uow, workflow_id, owner_id)

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


async def cancel_workflow(
    uow: UnitOfWork, workflow_id: uuid.UUID, *, owner_id: uuid.UUID, actor: str
) -> ProductWorkflow:
    """Stop a running campaign.

    Nothing is deleted. Queued messages may still be delivered afterwards; the
    actors reload the workflow and stop on the state they find, so cancelling is
    a decision recorded here rather than a reach into the queue.

    Cancelling an already-cancelled or published workflow raises
    ``IllegalTransitionError`` from the transition table.
    """
    workflow = await _owned_workflow(uow, workflow_id, owner_id)
    return await transition_workflow(
        uow,
        workflow_id,
        owner_id=owner_id,
        to_state=RunStatus.CANCELLED,
        expected_version=workflow.version,
        reason="Stopped by the owner",
        actor=actor,
    )


async def rerun_workflow(
    uow: UnitOfWork,
    workflow_id: uuid.UUID,
    *,
    owner_id: uuid.UUID,
    provider_mode: str,
    actor: str,
) -> ProductWorkflow:
    """Restart a cancelled campaign from the beginning.

    One transaction: CANCELLED → DRAFT → RESEARCH_QUEUED plus the queued run and
    its outbox message. A rerun that failed halfway would otherwise leave a
    workflow reset to DRAFT with nothing queued and no sign of why.

    The research itself is queued by :func:`queue_research_run`, the same path
    the manual trigger uses, so the budget gate cannot be skipped by rerunning.
    """
    workflow = await _owned_workflow(uow, workflow_id, owner_id)
    if workflow.state is not RunStatus.CANCELLED:
        raise IllegalTransitionError(
            workflow.state,
            RunStatus.DRAFT,
            "only a cancelled workflow can be rerun",
        )

    await uow.workflows.transition(
        workflow,
        to_state=RunStatus.DRAFT,
        expected_version=workflow.version,
        reason="Rerun requested by the owner",
        actor=actor,
    )
    await queue_research_run(
        uow,
        workflow,
        provider_mode=provider_mode,
        actor=actor,
        reason="Rerun research trigger",
    )
    await uow.audit.record(
        action=AuditAction.WORKFLOW_TRANSITION,
        entity_type="ProductWorkflow",
        entity_id=workflow.id,
        workflow_id=workflow.id,
        actor=actor,
        summary=f"{RunStatus.CANCELLED} → {RunStatus.RESEARCH_QUEUED} (rerun)",
        before={"state": RunStatus.CANCELLED.value},
        after={"state": RunStatus.RESEARCH_QUEUED.value, "version": workflow.version},
    )
    await uow.commit()
    return workflow


async def archive_workflow(
    uow: UnitOfWork, workflow_id: uuid.UUID, *, owner_id: uuid.UUID, actor: str
) -> ProductWorkflow:
    """Remove a campaign from the owner's list without destroying its record.

    "Delete" in the interface means archive here. The evidence, approvals, cost
    ledger and audit trail behind a campaign are exactly what CLAUDE.md forbids
    normal flows from deleting, so the row is stamped and filtered out of every
    listing instead of being removed.

    A campaign a worker is still running cannot be archived: the job would keep
    writing to something the owner believes is gone. Stop it first.
    """
    workflow = await _owned_workflow(uow, workflow_id, owner_id)

    if workflow.state in IN_FLIGHT_STATUSES:
        raise IllegalTransitionError(
            workflow.state,
            workflow.state,
            "stop the campaign before deleting it",
        )

    if workflow.archived_at is not None:
        # Already gone from the owner's point of view. Saying so again would
        # only add a second audit entry for one decision.
        return workflow

    workflow.archived_at = datetime.now(UTC)
    await uow.audit.record(
        action=AuditAction.ARCHIVED,
        entity_type="ProductWorkflow",
        entity_id=workflow.id,
        workflow_id=workflow.id,
        actor=actor,
        summary=f"Campaign archived from {workflow.state}",
        after={"archived_at": workflow.archived_at.isoformat()},
    )
    await uow.commit()
    return workflow


async def decide_gate(
    uow: UnitOfWork,
    workflow_id: uuid.UUID,
    *,
    owner_id: uuid.UUID,
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
    # Ownership first: nothing below may confirm that a concept ID exists to a
    # caller who does not own the workflow it belongs to.
    workflow = await _owned_workflow(uow, workflow_id, owner_id)

    # The same decision on the same target version is a duplicate click or a
    # redelivered Telegram callback, not a second approval. Return the original
    # record so the audit history holds one decision per reviewed version.
    for existing in await uow.approvals.history(workflow_id, gate=gate):
        if (
            existing.decision == decision
            and existing.target_id == target_id
            and existing.target_version == target_version
        ):
            return existing

    concept = None
    if target_type == "ProductConcept" and target_id is not None:
        concept = await uow.concepts.get(target_id)
        if not concept or concept.workflow_id != workflow_id:
            raise EntityNotFoundError("ProductConcept", target_id)

        # An approval names the version the human actually read. If a newer
        # prompt version was appended since, the decision is about text nobody
        # reviewed, so it is refused rather than silently applied to the latest.
        prompts = await uow.concepts.prompts(target_id)
        latest_version = prompts[-1].version if prompts else 1
        if target_version is not None and target_version < latest_version:
            raise ConcurrentModificationError(
                "ProductConcept", target_id, target_version, latest_version
            )

        # The IP screen is preliminary and never clears anything, but an
        # unresolved high-risk flag must be revised away rather than approved
        # over. Revising appends a version, which re-runs the screen.
        if decision == ApprovalDecision.APPROVED and concept.risk_level == RiskLevel.HIGH:
            raise UnresolvedRiskError(target_id)
    elif target_type == "Asset" and target_id is not None:
        asset = await uow.assets.get(target_id)
        if not asset or asset.workflow_id != workflow_id:
            raise EntityNotFoundError("Asset", target_id)

    previous_state = workflow.state
    # Raises GateNotSatisfiedError when the workflow is not at this gate.
    resulting_state = apply_approval(previous_state, gate, decision=decision)

    if concept is not None:
        if decision == ApprovalDecision.APPROVED:
            concept.status = ConceptStatus.APPROVED
        elif decision == ApprovalDecision.REJECTED:
            concept.status = ConceptStatus.REJECTED

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


async def get_workflow(
    uow: UnitOfWork, workflow_id: uuid.UUID, *, owner_id: uuid.UUID
) -> ProductWorkflow:
    return await _owned_workflow(uow, workflow_id, owner_id)


async def get_original_idea(
    uow: UnitOfWork, workflow_id: uuid.UUID, *, owner_id: uuid.UUID
) -> OriginalIdea:
    """The preserved idea for a workflow this owner owns."""
    await _owned_workflow(uow, workflow_id, owner_id)
    idea = await uow.ideas.get_for_workflow(workflow_id)
    if idea is None:
        raise EntityNotFoundError("OriginalIdea", workflow_id)
    return idea


async def list_workflows(
    uow: UnitOfWork,
    *,
    owner_id: uuid.UUID,
    state: RunStatus | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[ProductWorkflow], int]:
    """Always owner-scoped.

    ``owner_id`` is required rather than optional: an optional filter is one
    forgotten argument away from listing every workflow in the database.
    """
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


async def get_timeline(
    uow: UnitOfWork, workflow_id: uuid.UUID, *, owner_id: uuid.UUID
) -> list[TimelineEntry]:
    """Transitions, approvals and audit events merged into one ordered story."""
    await _owned_workflow(uow, workflow_id, owner_id)

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
