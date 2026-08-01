"""Concept repository and prompt versioning."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ConceptStatus
from app.infrastructure.models import DesignPrompt, ProductConcept


class SqlConceptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, concept: ProductConcept) -> ProductConcept:
        self._session.add(concept)
        await self._session.flush()
        return concept

    async def get(self, concept_id: uuid.UUID) -> ProductConcept | None:
        return await self._session.get(ProductConcept, concept_id)

    async def list_for_workflow(
        self, workflow_id: uuid.UUID, *, include_archived: bool = True
    ) -> Sequence[ProductConcept]:
        stmt = select(ProductConcept).where(ProductConcept.workflow_id == workflow_id)
        if not include_archived:
            stmt = stmt.where(ProductConcept.status != ConceptStatus.ARCHIVED)
        # Highest score first; unscored concepts last rather than dropped.
        stmt = stmt.order_by(ProductConcept.score.desc().nullslast(), ProductConcept.created_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def next_prompt_version(self, concept_id: uuid.UUID) -> int:
        """One past the highest existing version, or 1 if there are none."""
        result = await self._session.execute(
            select(DesignPrompt.version)
            .where(DesignPrompt.concept_id == concept_id)
            .order_by(DesignPrompt.version.desc())
            .limit(1)
        )
        highest = result.scalar_one_or_none()
        return 1 if highest is None else highest + 1

    async def add_prompt_version(
        self,
        concept: ProductConcept,
        *,
        positive_prompt: str,
        negative_prompt: str,
        typography_instructions: str | None = None,
        exact_slogan: str | None = None,
        change_note: str | None = None,
        intended_product_uses: list[str] | None = None,
        style_notes: str | None = None,
        palette: str | None = None,
        post_generation_checklist: list[str] | None = None,
        generation_metadata: dict[str, object] | None = None,
    ) -> DesignPrompt:
        """Append the next prompt version.

        Existing versions are never touched: an asset generated from version 2
        must stay traceable to version 2 even after version 3 exists.
        """
        prompt = DesignPrompt(
            concept_id=concept.id,
            version=await self.next_prompt_version(concept.id),
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            typography_instructions=typography_instructions,
            exact_slogan=exact_slogan,
            change_note=change_note,
            intended_product_uses=intended_product_uses or [],
            style_notes=style_notes,
            palette=palette,
            post_generation_checklist=post_generation_checklist or [],
            generation_metadata=generation_metadata or {},
        )
        self._session.add(prompt)
        await self._session.flush()
        return prompt

    async def prompts(self, concept_id: uuid.UUID) -> Sequence[DesignPrompt]:
        result = await self._session.execute(
            select(DesignPrompt)
            .where(DesignPrompt.concept_id == concept_id)
            .order_by(DesignPrompt.version)
        )
        return result.scalars().all()
