"""Production jobs and Etsy listing draft metadata."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.workflow import JobStatus, RiskLevel
from app.infrastructure.models.base import (
    Base,
    TimestampMixin,
    UuidMixin,
    pg_enum,
    timestamp_column,
)

if TYPE_CHECKING:
    from app.infrastructure.models.workflow import ProductWorkflow


class ProductionJob(UuidMixin, TimestampMixin, Base):
    """One run of the asset production pipeline.

    The operations themselves land in Phase 7; this records what was asked for,
    what came out and whether QA passed.
    """

    __tablename__ = "production_jobs"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: The approved artwork this job starts from. RESTRICT so the master cannot
    #: be deleted while a production job still references it.
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=True
    )
    output_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )

    #: Ordered operation names: remove_background, trim, typography, upscale, ...
    operations: Mapped[list[str]] = mapped_column(ARRAY(String(60)), nullable=False, default=list)
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: The QA report: dimensions, alpha, margins, opaque corners, spelling.
    #: Advisory — it flags problems, it does not replace artwork approval.
    qa_report: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    qa_passed: Mapped[bool | None] = mapped_column(nullable=True)

    started_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    completed_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    failure_kind: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="production_jobs")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_production_job_idempotency_key"),
        Index("ix_production_jobs_workflow_status", "workflow_id", "status"),
        CheckConstraint("attempt_count >= 0", name="production_attempt_non_negative"),
    )


class ListingDraft(UuidMixin, TimestampMixin, Base):
    """The listing as it will be sent to Etsy, plus the IP review behind it.

    There is no ``published_at`` column and no publish flag. The application
    creates drafts; if the owner publishes, that is recorded as a workflow state
    change with their name on it, not as a property of the draft.
    """

    __tablename__ = "listing_drafts"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    #: Validated against the Etsy limits in packages/domain/src/tags.ts (max 13,
    #: 20 characters each, unique after normalisation).
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)

    #: Minor units. Never a float, and never rendered as one.
    price_minor_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    taxonomy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Required by Etsy when a listing uses AI-generated imagery.
    ai_disclosure: Mapped[str | None] = mapped_column(Text, nullable=True)
    licence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Preliminary IP review --------------------------------------------
    #: What was screened. Never a clearance search; RiskLevel has no "safe".
    ip_reviewed_phrase: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ip_risk_level: Mapped[RiskLevel] = mapped_column(
        pg_enum(RiskLevel, "risk_level"), nullable=False, default=RiskLevel.UNKNOWN
    )
    ip_findings: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    #: The owner's explicit acknowledgement that this is not legal advice.
    #: Gate 3 cannot be approved without it.
    ip_acknowledged_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    ip_acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # --- Etsy ---------------------------------------------------------------
    #: Set once the draft exists in Etsy. Unique, so a resumed partial failure
    #: cannot create a second listing.
    etsy_shop_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    etsy_listing_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    etsy_listing_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    etsy_state: Mapped[str | None] = mapped_column(String(30), nullable=True, default="draft")
    etsy_image_ids: Mapped[list[str]] = mapped_column(ARRAY(String(60)), nullable=False, default=list)
    etsy_file_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    etsy_dispatch_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_started")
    etsy_last_synced_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    etsy_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    etsy_draft_created_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    #: Optimistic lock for the listing editor: an approval made against version N
    #: is stale once an edit bumps it to N+1.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="listing_draft")

    __table_args__ = (
        UniqueConstraint("etsy_listing_id", name="uq_listing_draft_etsy_listing_id"),
        CheckConstraint(
            "price_minor_units IS NULL OR price_minor_units >= 0",
            name="listing_price_non_negative",
        ),
        CheckConstraint("cardinality(tags) <= 13", name="listing_tag_limit"),
        CheckConstraint("version >= 1", name="listing_version_positive"),
    )
