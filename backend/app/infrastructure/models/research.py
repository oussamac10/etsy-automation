"""Research runs, evidence and keyword clusters.

Phase 2 provides the storage only. Nothing here calls a provider, and no row is
ever populated with an invented number — see the note on
:class:`ResearchEvidence`.
"""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    CompetitionLevel,
    ConfidenceLevel,
    Seasonality,
    SignalStrength,
    SourceType,
)
from app.domain.workflow import JobStatus
from app.infrastructure.models.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidMixin,
    pg_enum,
    timestamp_column,
)

if TYPE_CHECKING:
    from app.infrastructure.models.workflow import ProductWorkflow


class ResearchRun(UuidMixin, TimestampMixin, Base):
    """One execution of the research step.

    A workflow can have several: a revision request at the idea gate produces a
    new run rather than mutating the old one, so the evidence behind each set of
    concepts stays intact.
    """

    __tablename__ = "research_runs"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: 1-based, unique per workflow.
    run_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED
    )

    #: The query angles actually run. At least three are required by CLAUDE.md;
    #: the list is stored so a thin run is visible rather than implied.
    query_angles: Mapped[list[str]] = mapped_column(ARRAY(String(60)), nullable=False, default=list)

    #: How much the gathered evidence actually supports a conclusion. A run with
    #: thin evidence is labelled LOW, never padded.
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        pg_enum(ConfidenceLevel, "confidence_level"),
        nullable=False,
        default=ConfidenceLevel.LOW,
    )
    #: What to test when confidence is low. Free text, written by the synthesis
    #: step in Phase 5.
    proposed_test: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    completed_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="research_runs")
    evidence: Mapped[list[ResearchEvidence]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    keyword_clusters: Mapped[list[KeywordCluster]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_research_runs_workflow_number", "workflow_id", "run_number", unique=True),
        CheckConstraint("run_number >= 1", name="run_number_positive"),
    )


class ResearchEvidence(UuidMixin, CreatedAtMixin, Base):
    """One cited source.

    ``observation`` is what the source states. ``inference`` is what we concluded
    from it. They are separate columns, not one blended note, because the product
    must be able to show a reader which is which.

    No column here holds a search volume, sales count or revenue figure. Signals
    are qualitative enums backed by the observation text; inventing a number is
    forbidden by CLAUDE.md, and there is deliberately nowhere to put one.
    """

    __tablename__ = "research_evidence"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    search_query: Mapped[str] = mapped_column(Text, nullable=False)
    #: The angle this query represents: broad, long-tail, occasion, style, use-case.
    query_angle: Mapped[str] = mapped_column(String(60), nullable=False)

    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[SourceType] = mapped_column(
        pg_enum(SourceType, "source_type"), nullable=False
    )

    #: What the source says. Never model output.
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    #: What we concluded. Always model or human reasoning. Nullable: evidence may
    #: be recorded before anything is concluded from it.
    inference: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: When the source was read, which is not when the row was written.
    observed_at: Mapped[datetime] = timestamp_column(nullable=False)

    market: Mapped[str | None] = mapped_column(String(2), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    seasonality_signal: Mapped[Seasonality] = mapped_column(
        pg_enum(Seasonality, "seasonality"), nullable=False, default=Seasonality.UNKNOWN
    )
    competition_signal: Mapped[CompetitionLevel] = mapped_column(
        pg_enum(CompetitionLevel, "competition_level"),
        nullable=False,
        default=CompetitionLevel.UNKNOWN,
    )
    buyer_intent_signal: Mapped[SignalStrength] = mapped_column(
        pg_enum(SignalStrength, "signal_strength"),
        nullable=False,
        default=SignalStrength.UNKNOWN,
    )
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        pg_enum(ConfidenceLevel, "confidence_level"),
        nullable=False,
        default=ConfidenceLevel.LOW,
    )

    run: Mapped[ResearchRun] = relationship(back_populates="evidence")

    __table_args__ = (
        Index("ix_research_evidence_run_angle", "run_id", "query_angle"),
        CheckConstraint("length(observation) > 0", name="observation_not_empty"),
    )


class KeywordCluster(UuidMixin, CreatedAtMixin, Base):
    """Natural buyer language, grouped."""

    __tablename__ = "keyword_clusters"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: What the buyer types.
    primary_phrase: Mapped[str] = mapped_column(String(300), nullable=False)
    #: Colour, style, format, transparency.
    attributes: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)
    #: Mum, teacher, birthday, Halloween.
    recipient_occasion_terms: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)), nullable=False, default=list
    )
    #: Shirt, mug, sticker, wall art.
    use_case_terms: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)), nullable=False, default=list
    )

    market: Mapped[str] = mapped_column(String(2), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)

    competition_level: Mapped[CompetitionLevel] = mapped_column(
        pg_enum(CompetitionLevel, "competition_level"),
        nullable=False,
        default=CompetitionLevel.UNKNOWN,
    )
    #: What was actually seen that justifies competition_level. Required, so a
    #: judgement can never stand without its supporting observation.
    competition_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: 0-100 relative ordering within the run. Not a market metric and not
    #: presented as one.
    relevance_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    run: Mapped[ResearchRun] = relationship(back_populates="keyword_clusters")

    __table_args__ = (
        Index("ix_keyword_clusters_run_rank", "run_id", "relevance_rank"),
        CheckConstraint(
            "relevance_rank >= 0 AND relevance_rank <= 100", name="relevance_rank_range"
        ),
    )
