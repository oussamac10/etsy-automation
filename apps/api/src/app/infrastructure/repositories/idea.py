"""Original idea repository.

The whole point of this class is what it refuses to do: there is no method that
writes ``original_text`` after creation. :meth:`add_revision` appends instead,
and :meth:`guard_immutable` turns an attempted in-place edit into an explicit
error rather than a silent UPDATE.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import get_history

from app.domain.errors import ImmutableFieldError
from app.domain.ideas import normalize_idea_text
from app.infrastructure.models import OriginalIdea, OriginalIdeaRevision


class SqlIdeaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, idea: OriginalIdea) -> OriginalIdea:
        idea.normalized_text = normalize_idea_text(idea.original_text)
        self._session.add(idea)
        await self._session.flush()
        return idea

    async def get(self, idea_id: uuid.UUID) -> OriginalIdea | None:
        return await self._session.get(OriginalIdea, idea_id)

    async def get_for_workflow(self, workflow_id: uuid.UUID) -> OriginalIdea | None:
        result = await self._session.execute(
            select(OriginalIdea).where(OriginalIdea.workflow_id == workflow_id)
        )
        return result.scalar_one_or_none()

    def guard_immutable(self, idea: OriginalIdea) -> None:
        """Raise if ``original_text`` has been changed on a persisted instance.

        SQLAlchemy would happily flush an attribute assignment. This inspects the
        attribute's history and refuses, so a well-meaning "just fix the typo"
        becomes a visible error pointing at :meth:`add_revision`.
        """
        history = get_history(idea, "original_text")
        if history.has_changes() and history.deleted:
            raise ImmutableFieldError(
                "OriginalIdea",
                "original_text",
                "Record a new revision with add_revision() instead; the owner's "
                "original wording is never overwritten.",
            )

    async def add_revision(
        self,
        idea: OriginalIdea,
        *,
        revised_text: str,
        slogan: str | None = None,
        note: str | None = None,
        actor: str = "owner",
    ) -> OriginalIdeaRevision:
        """Append revision N+1 and leave ``original_text`` untouched."""
        self.guard_immutable(idea)

        revision = OriginalIdeaRevision(
            idea_id=idea.id,
            revision_number=idea.revision_count + 1,
            revised_text=revised_text,
            normalized_text=normalize_idea_text(revised_text),
            slogan=slogan,
            note=note,
            actor=actor,
        )
        idea.revision_count += 1
        self._session.add(revision)
        await self._session.flush()
        return revision

    async def revisions(self, idea_id: uuid.UUID) -> Sequence[OriginalIdeaRevision]:
        result = await self._session.execute(
            select(OriginalIdeaRevision)
            .where(OriginalIdeaRevision.idea_id == idea_id)
            .order_by(OriginalIdeaRevision.revision_number)
        )
        return result.scalars().all()
