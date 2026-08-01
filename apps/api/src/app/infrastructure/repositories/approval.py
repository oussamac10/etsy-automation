"""Approval repository. Append-only.

There is no update method and no delete method. Recording a second decision at
the same gate adds a row; the previous decision stays exactly as it was made.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus
from app.infrastructure.models import Approval, ProductWorkflow
from app.infrastructure.models.base import utc_now


class SqlApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        workflow: ProductWorkflow,
        gate: ApprovalGate,
        decision: ApprovalDecision,
        previous_state: RunStatus,
        resulting_state: RunStatus,
        actor: str,
        target_type: str,
        target_id: uuid.UUID | None = None,
        target_version: int | None = None,
        comment: str | None = None,
        revision_request: str | None = None,
        decided_at: datetime | None = None,
    ) -> Approval:
        """Append one decision.

        ``decided_at`` is left null for a PENDING request — an unanswered
        request is not a decision and should not look like one in the history.
        """
        approval = Approval(
            workflow_id=workflow.id,
            gate=gate,
            decision=decision,
            actor=actor,
            decided_at=(
                None if decision is ApprovalDecision.PENDING else (decided_at or utc_now())
            ),
            comment=comment,
            revision_request=revision_request,
            previous_state=previous_state,
            resulting_state=resulting_state,
            target_type=target_type,
            target_id=target_id,
            target_version=target_version,
        )
        self._session.add(approval)
        await self._session.flush()
        return approval

    async def history(
        self, workflow_id: uuid.UUID, *, gate: ApprovalGate | None = None
    ) -> Sequence[Approval]:
        """Every decision, oldest first. Nothing is ever filtered out."""
        stmt = select(Approval).where(Approval.workflow_id == workflow_id)
        if gate is not None:
            stmt = stmt.where(Approval.gate == gate)
        stmt = stmt.order_by(Approval.created_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def latest(self, workflow_id: uuid.UUID, gate: ApprovalGate) -> Approval | None:
        result = await self._session.execute(
            select(Approval)
            .where(Approval.workflow_id == workflow_id, Approval.gate == gate)
            .order_by(Approval.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def is_approved(self, workflow_id: uuid.UUID, gate: ApprovalGate) -> bool:
        """True only when the *most recent* decision at the gate is APPROVED.

        Reading the latest decision rather than "any approval exists" is what
        makes a later rejection or revision request actually revoke the gate.
        """
        latest = await self.latest(workflow_id, gate)
        return latest is not None and latest.decision is ApprovalDecision.APPROVED
