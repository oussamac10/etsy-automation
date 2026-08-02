"""Artwork generation records and asset metadata.

Phase 2 stores the shape of a generation; it never calls a provider. Every
column that would hold a provider result is nullable, because Phase 2 rows are
created in the QUEUED state and filled in by Phase 6.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    from app.infrastructure.models.concept import DesignPrompt, ProductConcept
    from app.infrastructure.models.cost import ProviderUsage
    from app.infrastructure.models.workflow import ProductWorkflow


class ArtworkJob(UuidMixin, TimestampMixin, Base):
    """One artwork generation attempt."""

    __tablename__ = "artwork_jobs"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_concepts.id", ondelete="CASCADE"), nullable=False
    )
    #: RESTRICT, not CASCADE: an asset must always be traceable to the exact
    #: prompt version that produced it, so that version cannot be deleted.
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_prompts.id", ondelete="RESTRICT"), nullable=False
    )

    provider: Mapped[ProviderName] = mapped_column(
        pg_enum(ProviderName, "provider_name"), nullable=False
    )
    provider_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: The provider's own job identifier, once it has one.
    provider_job_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: Derived from the inputs that determine the result. Unique across the
    #: table, so a duplicate dispatch cannot create a second billable job.
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)

    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    requested_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality: Mapped[str | None] = mapped_column(String(40), nullable=True)

    started_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    completed_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    #: Category plus message, never a raw provider payload.
    failure_kind: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="artwork_jobs")
    concept: Mapped[ProductConcept] = relationship(back_populates="artwork_jobs")
    prompt: Mapped[DesignPrompt] = relationship(back_populates="artwork_jobs")
    assets: Mapped[list[Asset]] = relationship(back_populates="artwork_job", passive_deletes=True)
    usage: Mapped[list[ProviderUsage]] = relationship(
        back_populates="artwork_job", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_artwork_job_idempotency_key"),
        Index("ix_artwork_jobs_workflow_status", "workflow_id", "status"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
    )


class Asset(UuidMixin, TimestampMixin, Base):
    """A stored binary and its provenance.

    The bytes live in object storage; this row holds the key and the facts we
    measured about the file. Nothing here is taken on trust from a generator —
    dimensions and transparency are recorded after inspection.
    """

    __tablename__ = "assets"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Null for an uploaded or derived asset with no generation behind it.
    artwork_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artwork_jobs.id", ondelete="SET NULL"), nullable=True
    )
    #: The asset this one was derived from, so a production chain is traceable
    #: back to the untouched master.
    derived_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )

    #: Opaque object-storage key. Never a user-supplied path.
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: SHA-256 hex. Unique per workflow: the same bytes stored twice in one
    #: workflow is a duplicate, not a second asset.
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Measured, not requested. Null until the file has been inspected.
    has_alpha: Mapped[bool | None] = mapped_column(nullable=True)
    has_transparent_pixels: Mapped[bool | None] = mapped_column(nullable=True)

    #: What the image worker reported: dimensions, edges, opaque corners.
    quality_check: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    #: Which operations produced this file, in order.
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="assets")
    artwork_job: Mapped[ArtworkJob | None] = relationship(back_populates="assets")

    __table_args__ = (
        UniqueConstraint("workflow_id", "checksum_sha256", name="uq_asset_workflow_checksum"),
        Index("ix_assets_checksum", "checksum_sha256"),
        CheckConstraint("byte_size > 0", name="asset_byte_size_positive"),
        CheckConstraint("length(checksum_sha256) = 64", name="checksum_is_sha256"),
    )
