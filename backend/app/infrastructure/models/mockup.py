"""Mockup generation job model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
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

from app.domain.enums import ProviderName
from app.domain.workflow import JobStatus
from app.infrastructure.models.base import (
    Base,
    TimestampMixin,
    UuidMixin,
    pg_enum,
    timestamp_column,
)

if TYPE_CHECKING:
    from app.infrastructure.models.asset import Asset
    from app.infrastructure.models.listing import ProductionJob
    from app.infrastructure.models.workflow import ProductWorkflow


class MockupJob(UuidMixin, TimestampMixin, Base):
    """Tracks a single product mockup generation task.

    Isolates external provider task state (Printful task_key, polling, failure status)
    so worker restarts can resume seamlessly and individual product mockups can fail/retry
    without affecting the master PNG or the overall workflow.
    """

    __tablename__ = "mockup_jobs"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    production_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("production_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    master_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    output_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )

    provider: Mapped[ProviderName] = mapped_column(
        pg_enum(ProviderName, "provider_name"),
        nullable=False,
        default=ProviderName.PRINTFUL,
    )
    external_task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_type: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    placement: Mapped[str] = mapped_column(String(60), nullable=False, default="front")

    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_mockup_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    failure_kind: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    workflow: Mapped[ProductWorkflow] = relationship()
    production_job: Mapped[ProductionJob] = relationship()
    master_asset: Mapped[Asset] = relationship(foreign_keys=[master_asset_id])
    output_asset: Mapped[Asset | None] = relationship(foreign_keys=[output_asset_id])

    __table_args__ = (
        UniqueConstraint("production_job_id", "product_type", name="uq_mockup_job_production_product"),
        Index("ix_mockup_jobs_workflow_status", "workflow_id", "status"),
        CheckConstraint("attempt_count >= 0", name="mockup_attempt_non_negative"),
    )
