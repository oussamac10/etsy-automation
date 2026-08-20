"""SQLAlchemy repository for ListingDraft entities."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ConcurrentModificationError, EntityNotFoundError
from app.infrastructure.models import ListingDraft


_UNSET: object = object()


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
        taxonomy_path: str | None = None,
        quantity: int | None = None,
        sku: str | None = None,
        shop_section_id: str | None | object = _UNSET,
        shop_section_name: str | None | object = _UNSET,
        should_auto_renew: bool | None = None,
        etsy_properties: dict[str, object] | None = None,
        primary_mockup_asset_id: uuid.UUID | None | object = _UNSET,
        shopping_cart_summary: str | None = None,
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

        has_changes = False
        if title is not None and draft.title != title:
            draft.title = title
            has_changes = True
        if description is not None and draft.description != description:
            draft.description = description
            has_changes = True
        if tags is not None and draft.tags != tags:
            draft.tags = tags
            has_changes = True
        if price_minor_units is not None and draft.price_minor_units != price_minor_units:
            draft.price_minor_units = price_minor_units
            has_changes = True
        if currency is not None and draft.currency != currency:
            draft.currency = currency
            has_changes = True
        if taxonomy_id is not None and draft.taxonomy_id != taxonomy_id:
            draft.taxonomy_id = taxonomy_id
            has_changes = True
        if taxonomy_path is not None and draft.taxonomy_path != taxonomy_path:
            draft.taxonomy_path = taxonomy_path
            has_changes = True
        if quantity is not None and draft.quantity != quantity:
            draft.quantity = quantity
            has_changes = True
        if sku is not None and draft.sku != sku:
            draft.sku = sku
            has_changes = True
        if shop_section_id is not _UNSET and draft.shop_section_id != shop_section_id:
            draft.shop_section_id = shop_section_id if isinstance(shop_section_id, str) else None
            has_changes = True
        if shop_section_name is not _UNSET and draft.shop_section_name != shop_section_name:
            draft.shop_section_name = shop_section_name if isinstance(shop_section_name, str) else None
            has_changes = True
        if should_auto_renew is not None and draft.should_auto_renew != should_auto_renew:
            draft.should_auto_renew = should_auto_renew
            has_changes = True
        if etsy_properties is not None and draft.etsy_properties != etsy_properties:
            draft.etsy_properties = etsy_properties
            has_changes = True
        if primary_mockup_asset_id is not _UNSET and draft.primary_mockup_asset_id != primary_mockup_asset_id:
            draft.primary_mockup_asset_id = primary_mockup_asset_id if isinstance(primary_mockup_asset_id, uuid.UUID) else None
            has_changes = True
        if shopping_cart_summary is not None and draft.shopping_cart_summary != shopping_cart_summary:
            draft.shopping_cart_summary = shopping_cart_summary
            has_changes = True
        if ai_disclosure is not None and draft.ai_disclosure != ai_disclosure:
            draft.ai_disclosure = ai_disclosure
            has_changes = True
        if licence_text is not None and draft.licence_text != licence_text:
            draft.licence_text = licence_text
            has_changes = True
        if customer_instructions is not None and draft.customer_instructions != customer_instructions:
            draft.customer_instructions = customer_instructions
            has_changes = True

        if has_changes:
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

    async def update_etsy_draft(
        self,
        draft_id: uuid.UUID,
        *,
        etsy_shop_id: str,
        etsy_listing_id: str,
        etsy_listing_url: str | None = None,
        etsy_state: str = "draft",
        etsy_draft_created_at: datetime | None = None,
        etsy_dispatch_status: str = "creating_listing",
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        draft.etsy_shop_id = etsy_shop_id
        draft.etsy_listing_id = etsy_listing_id
        draft.etsy_listing_url = etsy_listing_url
        draft.etsy_state = etsy_state
        draft.etsy_draft_created_at = etsy_draft_created_at or datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None)
        draft.etsy_dispatch_status = etsy_dispatch_status
        draft.etsy_last_synced_at = draft.etsy_draft_created_at
        await self._session.flush()
        return draft

    async def record_etsy_image_upload(
        self,
        draft_id: uuid.UUID,
        *,
        image_id: str,
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        current_images = list(draft.etsy_image_ids or [])
        if image_id not in current_images:
            current_images.append(image_id)
            draft.etsy_image_ids = current_images
        await self._session.flush()
        return draft

    async def record_etsy_file_upload(
        self,
        draft_id: uuid.UUID,
        *,
        file_id: str,
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        draft.etsy_file_id = file_id
        current_files = list(draft.etsy_file_ids or [])
        if file_id not in current_files:
            current_files.append(file_id)
            draft.etsy_file_ids = current_files
        await self._session.flush()
        return draft

    async def update_etsy_dispatch_status(
        self,
        draft_id: uuid.UUID,
        *,
        status: str,
        failure_reason: str | None = None,
        last_synced_at: datetime | None = None,
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        draft.etsy_dispatch_status = status
        if failure_reason is not None:
            draft.etsy_failure_reason = failure_reason
        if last_synced_at is not None:
            draft.etsy_last_synced_at = last_synced_at
        await self._session.flush()
        return draft

    async def clear_etsy_draft_state(
        self,
        draft_id: uuid.UUID,
        *,
        last_synced_at: datetime | None = None,
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        draft.etsy_shop_id = None
        draft.etsy_listing_id = None
        draft.etsy_listing_url = None
        draft.etsy_state = None
        draft.etsy_image_ids = []
        draft.etsy_file_id = None
        draft.etsy_file_ids = []
        draft.etsy_draft_created_at = None
        draft.etsy_dispatch_status = "not_started"
        draft.etsy_failure_reason = None
        draft.etsy_verification_status = None
        draft.etsy_verified_at = None
        draft.etsy_verification_result = {}
        draft.etsy_last_synced_at = last_synced_at or datetime.now(UTC)
        await self._session.flush()
        return draft

    async def update_etsy_verification(
        self,
        draft_id: uuid.UUID,
        *,
        status: str,
        verified_at: datetime,
        result: dict[str, object],
    ) -> ListingDraft:
        draft = await self.get(draft_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", draft_id)

        draft.etsy_verification_status = status
        draft.etsy_verified_at = verified_at
        draft.etsy_verification_result = result
        await self._session.flush()
        return draft

    async def list_distinct_shop_sections_for_user(
        self,
        owner_id: uuid.UUID,
    ) -> list[tuple[str | None, str | None]]:
        from app.infrastructure.models.workflow import ProductWorkflow

        stmt = (
            select(ListingDraft.shop_section_id, ListingDraft.shop_section_name)
            .join(ProductWorkflow, ListingDraft.workflow_id == ProductWorkflow.id)
            .where(ProductWorkflow.owner_id == owner_id)
            .where(
                (ListingDraft.shop_section_id.is_not(None))
                | (ListingDraft.shop_section_name.is_not(None))
            )
            .distinct()
        )
        res = await self._session.execute(stmt)
        return [(r[0], r[1]) for r in res.all() if r[0] or r[1]]


