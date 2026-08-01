"""The product workflow aggregate and its transition history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import IdeaMode
from app.domain.workflow import RunStatus
from app.infrastructure.models.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidMixin,
    pg_enum,
    timestamp_column,
)

if TYPE_CHECKING:
    from app.infrastructure.models.approval import Approval
    from app.infrastructure.models.artwork import ArtworkJob, Asset
    from app.infrastructure.models.audit import AuditEvent, WorkflowFailure
    from app.infrastructure.models.concept import ProductConcept
    from app.infrastructure.models.cost import ProviderUsage
    from app.infrastructure.models.idea import OriginalIdea
    from app.infrastructure.models.listing import ListingDraft, ProductionJob
    from app.infrastructure.models.research import ResearchRun
    from app.infrastructure.models.user import User


class ProductWorkflow(UuidMixin, TimestampMixin, Base):
    """One product being taken from idea to Etsy draft.

    This is the aggregate root: the state machine, the gates, the cost ledger and
    the audit trail all hang off it.
    """

    __tablename__ = "product_workflows"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: Fixed at creation. Decides whether an original idea is required and which
    #: concept origins are legitimate (see app/domain/ideas.py).
    idea_mode: Mapped[IdeaMode] = mapped_column(pg_enum(IdeaMode, "idea_mode"), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # --- Brief -------------------------------------------------------------
    target_marketplace: Mapped[str] = mapped_column(String(50), nullable=False, default="etsy")
    target_country: Mapped[str] = mapped_column(String(2), nullable=False)
    output_language: Mapped[str] = mapped_column(String(10), nullable=False)
    target_buyer: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Intended physical products, stored as the ProductUse enum's values.
    intended_product_uses: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list
    )

    # --- State -------------------------------------------------------------
    state: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"),
        nullable=False,
        default=RunStatus.DRAFT,
    )
    #: Optimistic lock. Every state change bumps it, and a compare-and-set update
    #: that finds a different value raises ConcurrentModificationError rather
    #: than applying a decision made against stale data.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    archived_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    # --- Relationships -----------------------------------------------------
    owner: Mapped[User] = relationship(back_populates="workflows")

    original_idea: Mapped[OriginalIdea | None] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    research_runs: Mapped[list[ResearchRun]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    concepts: Mapped[list[ProductConcept]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    artwork_jobs: Mapped[list[ArtworkJob]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    assets: Mapped[list[Asset]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    production_jobs: Mapped[list[ProductionJob]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    listing_draft: Mapped[ListingDraft | None] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    provider_usage: Mapped[list[ProviderUsage]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    transitions: Mapped[list[WorkflowTransition]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    failures: Mapped[list[WorkflowFailure]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_product_workflows_owner_state", "owner_id", "state"),
        Index("ix_product_workflows_created_at", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ProductWorkflow {self.id} {self.idea_mode} {self.state}>"


class WorkflowTransition(UuidMixin, CreatedAtMixin, Base):
    """One recorded state change. Append-only.

    Every successful transition writes a row here *and* an audit event. The two
    serve different readers: this table is the workflow's own timeline, the audit
    log is the cross-entity history.
    """

    __tablename__ = "workflow_transitions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Null for the very first row, which records the workflow's creation.
    from_state: Mapped[RunStatus | None] = mapped_column(
        pg_enum(RunStatus, "run_status"), nullable=True
    )
    to_state: Mapped[RunStatus] = mapped_column(pg_enum(RunStatus, "run_status"), nullable=False)
    #: Why it moved: "approval:IDEA_APPROVAL", "job:research_completed", ...
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="system")
    #: The workflow version *after* this transition, so the timeline can be
    #: replayed and cross-checked against the aggregate.
    resulting_version: Mapped[int] = mapped_column(Integer, nullable=False)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="transitions")

    __table_args__ = (
        Index("ix_workflow_transitions_workflow_created", "workflow_id", "created_at"),
    )
