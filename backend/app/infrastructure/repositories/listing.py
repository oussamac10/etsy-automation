"""SQLAlchemy repository for ListingDraft entities."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ConcurrentModificationError, EntityNotFoundError
from app.infrastructure.models import ListingDraft


class SqlListingDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: ListingDraft) -> ListingDraft:
        self._session.add(draft)
        await self._session.flush()
        return draft

    async def get(self, draft_id: uuid.UUID) -> ListingDraft | None:
        return await self._session.get(ListingDraft, draft_id)

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> ListingDraft | None:
        result = await self._session.execute(
            select(ListingDraft).where(ListingDraft.workflow_id == workflow_id)
        )
        return result.scalars().first()

    async def update(
        self,
        draft_id: uuid.UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        price_minor_units: int | None = None,
        currency: str | None = None,
        taxonomy_id: int | None = None,
        ai_disclosure: str | None = None,
        licence_text: str | None = None,
        customer_instructions: str | None = None,
        expected_version: int | None = None,
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        if expected_version is not None and draft.version != expected_version:
            raise ConcurrentModificationError(
                "ListingDraft", draft_id, expected_version, draft.version
            )

        if title is not None:
            draft.title = title
        if description is not None:
            draft.description = description
        if tags is not None:
            draft.tags = tags
        if price_minor_units is not None:
            draft.price_minor_units = price_minor_units
        if currency is not None:
            draft.currency = currency
        if taxonomy_id is not None:
            draft.taxonomy_id = taxonomy_id
        if ai_disclosure is not None:
            draft.ai_disclosure = ai_disclosure
        if licence_text is not None:
            draft.licence_text = licence_text
        if customer_instructions is not None:
            draft.customer_instructions = customer_instructions

        draft.version += 1
        await self._session.flush()
        return draft

    async def update_ip_review(
        self,
        draft_id: uuid.UUID,
        *,
        ip_reviewed_phrase: str | None,
        ip_risk_level: object,
        ip_findings: dict[str, object],
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        draft.ip_reviewed_phrase = ip_reviewed_phrase
        draft.ip_risk_level = ip_risk_level  # type: ignore[assignment]
        draft.ip_findings = ip_findings
        await self._session.flush()
        return draft

    async def acknowledge_ip_risk(
        self,
        draft_id: uuid.UUID,
        *,
        acknowledged_by: str,
        acknowledged_at: datetime,
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        draft.ip_acknowledged_by = acknowledged_by
        draft.ip_acknowledged_at = acknowledged_at
        await self._session.flush()
        return draft
