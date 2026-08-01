"""Product concepts and their versioned design prompts."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ConceptOrigin, ConceptStatus, Seasonality
from app.domain.workflow import RiskLevel
from app.infrastructure.models.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidMixin,
    pg_enum,
)

if TYPE_CHECKING:
    from app.infrastructure.models.artwork import ArtworkJob
    from app.infrastructure.models.idea import OriginalIdea
    from app.infrastructure.models.workflow import ProductWorkflow


class ProductConcept(UuidMixin, TimestampMixin, Base):
    """One proposed product.

    A concept never overwrites the owner's original idea. When it is derived from
    one, ``original_idea_id`` points back at the preserved record and ``origin``
    is ``USER`` or ``HYBRID``.
    """

    __tablename__ = "product_concepts"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Set when the concept was derived from the owner's idea. Null for
    #: market-only proposals. ``SET NULL`` on delete rather than cascade: losing
    #: the link must not silently delete a concept the owner approved.
    original_idea_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("original_ideas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: The research run that produced it. Null for a concept typed in directly.
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_runs.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    origin: Mapped[ConceptOrigin] = mapped_column(
        pg_enum(ConceptOrigin, "concept_origin"), nullable=False
    )

    #: The real point of difference. Required: "the same but prettier" is not a
    #: differentiator, and leaving this empty hides that.
    differentiation: Mapped[str] = mapped_column(Text, nullable=False)
    target_buyer: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyer_use_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    bundle_potential: Mapped[str | None] = mapped_column(Text, nullable=True)
    intended_product_uses: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list
    )

    seasonality: Mapped[Seasonality] = mapped_column(
        pg_enum(Seasonality, "seasonality"), nullable=False, default=Seasonality.UNKNOWN
    )

    #: Preliminary only. Never a clearance conclusion; RiskLevel has no "safe".
    risk_level: Mapped[RiskLevel] = mapped_column(
        pg_enum(RiskLevel, "risk_level"), nullable=False, default=RiskLevel.UNKNOWN
    )
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Weighted total, 1.00-5.00. Numeric, not float: a score that drives ranking
    #: should compare exactly.
    score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    #: The seven components behind the total, so a reviewer sees *why* a concept
    #: scored what it did rather than only the number.
    score_breakdown: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    score_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: A low score never deletes or auto-rejects a concept. Setting a concept
    #: aside is ARCHIVED; only a human decision at the gate produces REJECTED.
    status: Mapped[ConceptStatus] = mapped_column(
        pg_enum(ConceptStatus, "concept_status"),
        nullable=False,
        default=ConceptStatus.PROPOSED,
    )

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="concepts")
    original_idea: Mapped[OriginalIdea | None] = relationship(back_populates="concepts")
    prompts: Mapped[list[DesignPrompt]] = relationship(
        back_populates="concept",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DesignPrompt.version",
    )
    artwork_jobs: Mapped[list[ArtworkJob]] = relationship(back_populates="concept")

    __table_args__ = (
        Index("ix_product_concepts_workflow_status", "workflow_id", "status"),
        Index("ix_product_concepts_workflow_score", "workflow_id", "score"),
        CheckConstraint("score IS NULL OR (score >= 1.00 AND score <= 5.00)", name="score_range"),
        CheckConstraint("length(differentiation) > 0", name="differentiation_not_empty"),
    )

    @property
    def latest_prompt(self) -> DesignPrompt | None:
        """The highest-numbered prompt version, or None if none exists yet."""
        return self.prompts[-1] if self.prompts else None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ProductConcept {self.id} {self.origin} {self.status}>"


class DesignPrompt(UuidMixin, CreatedAtMixin, Base):
    """A versioned prompt pair for one concept. Append-only.

    Editing a prompt creates version N+1; earlier versions are never modified or
    deleted, so an artwork asset can always be traced to the exact prompt that
    produced it.
    """

    __tablename__ = "design_prompts"

    concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: 1-based, unique per concept.
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    positive_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    #: Required. A prompt without rejections invites backgrounds, watermarks and
    #: copied styles, so the column is NOT NULL by design.
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    #: Typography is separate from the prompt on purpose: when spelling matters
    #: the image model is told to produce *no text*, and the phrase below is
    #: rendered deterministically by the Phase 7 pipeline instead.
    typography_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    exact_slogan: Mapped[str | None] = mapped_column(String(300), nullable=True)

    intended_product_uses: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list
    )
    style_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    palette: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: What must be verified on the generated file — transparency, uncropped
    #: edges, dimensions. Generation never guarantees these; they are checked.
    post_generation_checklist: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )

    #: Provider-independent settings (aspect ratio, target pixels, quality tier).
    #: No provider SDK field names, no API keys.
    generation_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    concept: Mapped[ProductConcept] = relationship(back_populates="prompts")
    artwork_jobs: Mapped[list[ArtworkJob]] = relationship(back_populates="prompt")

    __table_args__ = (
        UniqueConstraint("concept_id", "version", name="uq_design_prompt_version"),
        CheckConstraint("version >= 1", name="prompt_version_positive"),
        CheckConstraint("length(negative_prompt) > 0", name="negative_prompt_not_empty"),
    )
