"""Provider usage and money.

Amounts are stored as integer minor units in ``BIGINT`` columns, never as
floats and never as ``NUMERIC`` that someone might read into a float on the way
past. The domain wraps them in :class:`app.domain.money.Money`.

An entry is written twice in its life: once as an ``ESTIMATED`` reservation
before dispatch, then ``RECONCILED`` with the units the provider actually
reported. Both amounts stay on the row, so the difference between what was
predicted and what was spent is visible rather than lost.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CostStatus, ProviderName
from app.infrastructure.models.base import (
    Base,
    TimestampMixin,
    UuidMixin,
    pg_enum,
)

if TYPE_CHECKING:
    from app.infrastructure.models.artwork import ArtworkJob
    from app.infrastructure.models.workflow import ProductWorkflow


class ProviderUsage(UuidMixin, TimestampMixin, Base):
    """One billable (or would-be billable) provider operation.

    Phase 2 can only record ``FAKE`` provider entries at zero cost, because no
    real adapter exists. The schema is complete so Phase 5 onwards has nothing to
    migrate when the first real call happens.
    """

    __tablename__ = "provider_usage"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artwork_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artwork_jobs.id", ondelete="SET NULL"), nullable=True
    )

    provider: Mapped[ProviderName] = mapped_column(
        pg_enum(ProviderName, "provider_name"), nullable=False
    )
    #: The model or service billed: "gpt-image-2", "V4.1 raster", "web_search".
    service: Mapped[str] = mapped_column(String(120), nullable=False)
    #: What was done: "image_generation", "text_synthesis", "background_removal".
    operation: Mapped[str] = mapped_column(String(80), nullable=False)

    #: Units as the provider counts them — tokens, images, requests.
    input_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    #: What input_units/output_units are counted in, so a reader is not guessing.
    unit_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="units")

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    #: Reserved against the budget before dispatch.
    estimated_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    #: Null until reconciliation. Not defaulted to the estimate: an unreconciled
    #: entry must be distinguishable from one that genuinely cost the estimate.
    actual_cost_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    status: Mapped[CostStatus] = mapped_column(
        pg_enum(CostStatus, "cost_status"), nullable=False, default=CostStatus.ESTIMATED
    )

    #: The price entry used, with its effective_from date and source URL, so an
    #: old entry can still be explained after prices change.
    price_reference: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    #: Ties the entry to the operation that caused it, so a duplicate delivery
    #: reconciles the same row instead of adding a second charge.
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="provider_usage")
    artwork_job: Mapped[ArtworkJob | None] = relationship(back_populates="usage")

    __table_args__ = (
        Index("ix_provider_usage_workflow_created", "workflow_id", "created_at"),
        Index("ix_provider_usage_provider_created", "provider", "created_at"),
        Index("ix_provider_usage_idempotency_key", "idempotency_key"),
        CheckConstraint("input_units >= 0", name="input_units_non_negative"),
        CheckConstraint("output_units >= 0", name="output_units_non_negative"),
        CheckConstraint("estimated_cost_minor >= 0", name="estimated_cost_non_negative"),
        CheckConstraint(
            "actual_cost_minor IS NULL OR actual_cost_minor >= 0",
            name="actual_cost_non_negative",
        ),
        CheckConstraint(
            "(status <> 'reconciled') OR (actual_cost_minor IS NOT NULL)",
            name="reconciled_requires_actual_cost",
        ),
    )

    @property
    def effective_cost_minor(self) -> int:
        """What this entry counts as right now.

        The actual amount once reconciled, otherwise the estimate — a budget
        check has to include work that is in flight.
        """
        if self.status is CostStatus.VOIDED:
            return 0
        return (
            self.actual_cost_minor
            if self.actual_cost_minor is not None
            else self.estimated_cost_minor
        )
