"""The owner's original idea, preserved verbatim.

The central rule of this module: ``OriginalIdea.original_text`` is written once
and never updated. A correction is a new :class:`OriginalIdeaRevision` row, so
the history of what the owner actually said is complete and ordered.

Optimised or research-derived wording lives in ``ProductConcept``, never here.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.models.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidMixin,
)

if TYPE_CHECKING:
    from app.infrastructure.models.concept import ProductConcept
    from app.infrastructure.models.workflow import ProductWorkflow


class OriginalIdea(UuidMixin, TimestampMixin, Base):
    """What the owner submitted, exactly as they wrote it.

    Only present for ``user-idea`` and ``hybrid`` workflows; ``market-led``
    starts without one. One per workflow, enforced by a unique constraint.
    """

    __tablename__ = "original_ideas"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_workflows.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    #: Immutable. The repository refuses to update it and
    #: ``test_original_idea_immutability`` proves it. Never rewritten by
    #: research, never replaced by an optimised version.
    original_text: Mapped[str] = mapped_column(Text, nullable=False)

    #: A comparison form (NFKC, collapsed whitespace, casefolded) stored *beside*
    #: the original for duplicate detection and search. Never shown as the
    #: owner's words.
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)

    #: The owner's exact slogan, kept apart from the descriptive text because it
    #: is rendered deterministically by the typography pipeline in Phase 7 and
    #: its spelling must survive untouched.
    slogan: Mapped[str | None] = mapped_column(String(300), nullable=True)

    desired_style: Mapped[str | None] = mapped_column(String(300), nullable=True)
    audience: Mapped[str | None] = mapped_column(String(300), nullable=True)
    occasion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    season: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_uses: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)

    #: Number of revisions recorded so far. 0 means the original still stands.
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    workflow: Mapped[ProductWorkflow] = relationship(back_populates="original_idea")
    revisions: Mapped[list[OriginalIdeaRevision]] = relationship(
        back_populates="idea",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OriginalIdeaRevision.revision_number",
        # Eager: `current_text` reads this list from a synchronous property, and
        # a lazy load there would attempt IO outside the async context.
        lazy="selectin",
    )
    concepts: Mapped[list[ProductConcept]] = relationship(back_populates="original_idea")

    __table_args__ = (
        CheckConstraint("length(original_text) >= 3", name="original_text_not_trivial"),
        CheckConstraint("revision_count >= 0", name="revision_count_non_negative"),
    )

    @property
    def current_text(self) -> str:
        """The latest wording the owner stands behind.

        Falls back to the original when there are no revisions. The original is
        still readable at ``original_text`` either way — a revision adds to the
        history, it does not erase what came before.
        """
        if not self.revisions:
            return self.original_text
        return self.revisions[-1].revised_text

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<OriginalIdea {self.id} revisions={self.revision_count}>"


class OriginalIdeaRevision(UuidMixin, CreatedAtMixin, Base):
    """A later version of the idea. Append-only.

    Revisions are numbered from 1 and unique per idea, so the sequence cannot
    develop gaps or duplicates even under concurrent writes.
    """

    __tablename__ = "original_idea_revisions"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("original_ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revised_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    slogan: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: Why the owner changed it. Free text, supplied by the owner.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(200), nullable=False, default="owner")

    idea: Mapped[OriginalIdea] = relationship(back_populates="revisions")

    __table_args__ = (
        UniqueConstraint("idea_id", "revision_number", name="uq_idea_revision_number"),
        CheckConstraint("revision_number >= 1", name="revision_number_positive"),
    )
