"""Human approval decisions. Append-only.

Every row is a decision that was actually made. Changing your mind writes
another row; it never edits an existing one. That is what makes the approval
history evidence rather than a status field.

An approval also records the **target version** of what was reviewed, so editing
a concept, prompt or listing after approval invalidates the approval instead of
silently inheriting it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus
from app.infrastructure.models.base import (
    Base,
    CreatedAtMixin,
    UuidMixin,
    pg_enum,
    timestamp_column,
)

if TYPE_CHECKING:
    from app.infrastructure.models.audit import AuditEvent
    from app.infrastructure.models.workflow import ProductWorkflow


class Approval(UuidMixin, CreatedAtMixin, Base):
    """One decision at one gate.

    There is no ``updated_at`` and no update path in the repository. The
    ``decided_at`` timestamp equals ``created_at`` for a real decision; a
    ``PENDING`` row is a request awaiting an answer and has none.
    """

    __tablename__ = "approvals"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    gate: Mapped[ApprovalGate] = mapped_column(
        pg_enum(ApprovalGate, "approval_gate"), nullable=False
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        pg_enum(ApprovalDecision, "approval_decision"),
        nullable=False,
        default=ApprovalDecision.PENDING,
    )

    #: Who decided. Phase 3 replaces this free-text actor with a user reference.
    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="owner")
    #: Null while the decision is PENDING; set once an answer is recorded.
    decided_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: What the reviewer asked to be changed, when decision is REVISION_REQUESTED.
    revision_request: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The workflow states either side of this decision, so the timeline is
    #: readable without replaying the whole transition table.
    previous_state: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"), nullable=False
    )
    resulting_state: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"), nullable=False
    )

    #: What was reviewed. An approval refers to a version, not only an entity ID.
    target_type: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    target_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="approvals")
    audit_events: Mapped[list[AuditEvent]] = relationship(
        back_populates="approval", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_approvals_workflow_gate_created", "workflow_id", "gate", "created_at"),
        CheckConstraint(
            "(decision <> 'REVISION_REQUESTED') OR (revision_request IS NOT NULL)",
            name="revision_requires_request_text",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Approval {self.id} {self.gate} {self.decision}>"
