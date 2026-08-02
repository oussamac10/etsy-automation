"""Audit events and workflow failures.

Both tables are append-only and are never deleted through normal application
flows (root CLAUDE.md). Neither carries an ``updated_at``, because nothing
updates them.

Audit metadata is structured JSON and must not contain a secret. The repository
runs the same redaction the logger uses before writing.
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AuditAction
from app.infrastructure.models.base import (
    Base,
    CreatedAtMixin,
    UuidMixin,
    pg_enum,
    timestamp_column,
)

if TYPE_CHECKING:
    from app.infrastructure.models.approval import Approval
    from app.infrastructure.models.workflow import ProductWorkflow


class AuditEvent(UuidMixin, CreatedAtMixin, Base):
    """One thing that happened. Append-only."""

    __tablename__ = "audit_events"

    #: Nullable so an event can outlive the workflow it described if retention
    #: rules ever detach one. In normal operation it is always set.
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True
    )

    action: Mapped[AuditAction] = mapped_column(
        pg_enum(AuditAction, "audit_action"), nullable=False
    )
    #: The entity this concerns: "ProductWorkflow", "Approval", "ProviderUsage".
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="system")
    #: Follows a request across web → api → worker.
    correlation_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    #: State either side of the change, small and structured. Never a full row
    #: dump and never a secret.
    before: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    summary: Mapped[str] = mapped_column(Text, nullable=False)

    workflow: Mapped[ProductWorkflow | None] = relationship(back_populates="audit_events")
    approval: Mapped[Approval | None] = relationship(back_populates="audit_events")

    __table_args__ = (
        Index("ix_audit_events_workflow_created", "workflow_id", "created_at"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_action_created", "action", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AuditEvent {self.id} {self.action} {self.entity_type}>"


class WorkflowFailure(UuidMixin, CreatedAtMixin, Base):
    """A failure and its retry history. Append-only.

    Separate from ``AuditEvent`` because a failure has a lifecycle a generic
    event does not: it is retried, and eventually either resolved or exhausted.
    """

    __tablename__ = "workflow_failures"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The FailureStatus value the workflow entered.
    failure_state: Mapped[str] = mapped_column(String(60), nullable=False)
    #: The stage it happened in, and the job if there was one.
    stage: Mapped[str] = mapped_column(String(60), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    #: The normalised ProviderErrorKind, so retry policy is queryable.
    error_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    #: Message only. Never a raw provider payload, never a connection string.
    error_message: Mapped[str] = mapped_column(Text, nullable=False)

    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retryable: Mapped[bool] = mapped_column(nullable=False, default=False)
    next_retry_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    #: Set when a retry succeeded or the owner abandoned the stage. A null value
    #: means the failure is still open.
    resolved_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="failures")

    __table_args__ = (
        Index("ix_workflow_failures_workflow_created", "workflow_id", "created_at"),
        CheckConstraint("attempt >= 1", name="failure_attempt_positive"),
    )
