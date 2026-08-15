"""Workflow repository, including the compare-and-set state transition."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ConcurrentModificationError
from app.domain.workflow import (
    ApprovalDecision,
    ApprovalGate,
    FailureStatus,
    IllegalTransitionError,
    RunStatus,
    advance,
    apply_approval,
)
from app.infrastructure.models import ProductWorkflow, WorkflowTransition


class SqlWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, workflow: ProductWorkflow) -> ProductWorkflow:
        self._session.add(workflow)
        await self._session.flush()
        return workflow

    async def get(self, workflow_id: uuid.UUID) -> ProductWorkflow | None:
        return await self._session.get(ProductWorkflow, workflow_id)

    async def list(
        self,
        *,
        owner_id: uuid.UUID | None = None,
        state: RunStatus | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ProductWorkflow]:
        stmt = select(ProductWorkflow).order_by(ProductWorkflow.created_at.desc())
        if owner_id is not None:
            stmt = stmt.where(ProductWorkflow.owner_id == owner_id)
        if state is not None:
            stmt = stmt.where(ProductWorkflow.state == state)
        if not include_archived:
            stmt = stmt.where(ProductWorkflow.archived_at.is_(None))
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        *,
        owner_id: uuid.UUID | None = None,
        state: RunStatus | None = None,
        include_archived: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(ProductWorkflow)
        if owner_id is not None:
            stmt = stmt.where(ProductWorkflow.owner_id == owner_id)
        if state is not None:
            stmt = stmt.where(ProductWorkflow.state == state)
        if not include_archived:
            stmt = stmt.where(ProductWorkflow.archived_at.is_(None))
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def transition(
        self,
        workflow: ProductWorkflow,
        *,
        to_state: RunStatus,
        expected_version: int,
        reason: str,
        actor: str = "system",
        gate: ApprovalGate | None = None,
        decision: ApprovalDecision | None = None,
    ) -> WorkflowTransition:
        """Move the workflow, or fail loudly.

        Order matters. The domain validates the move first, so an illegal
        transition never reaches the database. Then a conditional UPDATE bumps
        the version only if it still matches what the caller read — if another
        request moved the workflow in between, zero rows match and the caller's
        decision is rejected as stale rather than applied on top of someone
        else's change.

        Leaving a review state is the one move ``advance`` refuses, because a
        gate must not be bypassable by a plain transition. A caller acting on a
        human decision passes ``gate`` and ``decision``, and the move is
        validated by :func:`apply_approval` instead — so a gated state can still
        only be left by a recorded decision, never by an arbitrary request.
        """
        if gate is not None:
            if decision is None:
                raise ValueError("A gate transition requires the decision that caused it")
            expected = apply_approval(workflow.state, gate, decision=decision)
            if expected is not to_state:
                raise IllegalTransitionError(
                    workflow.state,
                    to_state,
                    f"gate {gate} with decision {decision} leads to {expected}",
                )
        else:
            # Raises IllegalTransitionError for a move the state machine forbids.
            advance(workflow.state, to_state)

        from_state = workflow.state
        new_version = expected_version + 1

        result = await self._session.execute(
            update(ProductWorkflow)
            .where(
                ProductWorkflow.id == workflow.id,
                ProductWorkflow.version == expected_version,
            )
            .values(state=to_state, version=new_version)
        )
        # A conditional UPDATE matching zero rows means the version moved.
        if result.rowcount != 1:  # type: ignore[attr-defined]
            await self._session.refresh(workflow)
            raise ConcurrentModificationError(
                "ProductWorkflow", workflow.id, expected_version, workflow.version
            )

        # Keep the in-memory instance consistent with the row we just wrote.
        await self._session.refresh(workflow)

        transition = WorkflowTransition(
            workflow_id=workflow.id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            actor=actor,
            resulting_version=new_version,
        )
        self._session.add(transition)
        await self._session.flush()
        return transition

    async def record_initial_state(
        self, workflow: ProductWorkflow, *, actor: str = "system"
    ) -> WorkflowTransition:
        """The first timeline row, with a null ``from_state``.

        Written at creation so the timeline starts where the workflow does
        rather than at its first move.
        """
        transition = WorkflowTransition(
            workflow_id=workflow.id,
            from_state=None,
            to_state=workflow.state,
            reason="workflow_created",
            actor=actor,
            resulting_version=workflow.version,
        )
        self._session.add(transition)
        await self._session.flush()
        return transition

    async def transitions(self, workflow_id: uuid.UUID) -> Sequence[WorkflowTransition]:
        result = await self._session.execute(
            select(WorkflowTransition)
            .where(WorkflowTransition.workflow_id == workflow_id)
            .order_by(WorkflowTransition.created_at, WorkflowTransition.resulting_version)
        )
        return result.scalars().all()
