"""SQLAlchemy repository for TrademarkRecord entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ip_risk import normalize_trademark_phrase
from app.infrastructure.models import TrademarkRecord


class SqlTrademarkRepository:
    """Repository for querying and managing local USPTO trademark records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: TrademarkRecord) -> TrademarkRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_serial(self, serial_number: str) -> TrademarkRecord | None:
        stmt = select(TrademarkRecord).where(TrademarkRecord.serial_number == serial_number)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_registration(self, registration_number: str) -> TrademarkRecord | None:
        stmt = select(TrademarkRecord).where(
            TrademarkRecord.registration_number == registration_number
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def search_by_phrase(
        self, phrase: str, limit: int = 25, live_only: bool | None = None
    ) -> list[TrademarkRecord]:
        """Search trademark records for a phrase using exact, substring, and pg_trgm similarity."""
        norm_phrase = normalize_trademark_phrase(phrase)
        if not norm_phrase or len(norm_phrase) < 2:
            return []

        # Exact, substring, or trigram similarity match via PostgreSQL pg_trgm
        similarity_expr = func.similarity(TrademarkRecord.normalized_mark_text, norm_phrase)

        match_criteria = or_(
            TrademarkRecord.normalized_mark_text == norm_phrase,
            TrademarkRecord.normalized_mark_text.ilike(f"%{norm_phrase}%"),
            TrademarkRecord.mark_text.ilike(f"%{phrase.strip()}%"),
            similarity_expr > 0.3,
        )

        stmt = select(TrademarkRecord).where(match_criteria)

        if live_only is True:
            stmt = stmt.where(TrademarkRecord.is_live.is_(True))
        elif live_only is False:
            stmt = stmt.where(TrademarkRecord.is_live.is_(False))

        stmt = stmt.order_by(
            (TrademarkRecord.normalized_mark_text == norm_phrase).desc(),
            TrademarkRecord.is_live.desc(),
            similarity_expr.desc(),
        ).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_source_date(self) -> datetime | None:
        """Get the most recent dataset source update or import timestamp."""
        stmt = select(
            func.coalesce(
                func.max(TrademarkRecord.source_updated_at),
                func.max(TrademarkRecord.imported_at),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> dict[str, int]:
        """Insert or update trademark records in bulk."""
        inserted = 0
        updated = 0
        failed = 0

        for item in records:
            try:
                mark_text = str(item.get("mark_text", "")).strip()
                if not mark_text:
                    continue
                norm_mark = normalize_trademark_phrase(mark_text)
                serial = str(item.get("serial_number")) if item.get("serial_number") else None

                existing: TrademarkRecord | None = None
                if serial:
                    existing = await self.get_by_serial(serial)

                if existing is None:
                    stmt = select(TrademarkRecord).where(
                        TrademarkRecord.normalized_mark_text == norm_mark
                    )
                    res = await self._session.execute(stmt)
                    existing = res.scalars().first()

                if existing:
                    existing.mark_text = mark_text
                    existing.normalized_mark_text = norm_mark
                    if item.get("status_code") is not None:
                        existing.status_code = str(item["status_code"])
                    status_val = item.get("status_text") or item.get("status")
                    if status_val:
                        existing.status_text = str(status_val)
                    existing.is_live = bool(item.get("is_live", existing.is_live))
                    existing.classes = list(item.get("classes", existing.classes))
                    if item.get("goods_services") is not None:
                        existing.goods_services = str(item["goods_services"])
                    owner_val = item.get("owner_name") or item.get("owner")
                    if owner_val is not None:
                        existing.owner_name = str(owner_val)
                    if item.get("filing_date") is not None:
                        existing.filing_date = str(item["filing_date"])
                    if item.get("registration_date") is not None:
                        existing.registration_date = str(item["registration_date"])
                    if item.get("source_file") is not None:
                        existing.source_file = str(item["source_file"])
                    if item.get("source_updated_at") is not None:
                        existing.source_updated_at = item["source_updated_at"]
                    updated += 1
                else:
                    new_rec = TrademarkRecord(
                        id=uuid.uuid4(),
                        mark_text=mark_text,
                        normalized_mark_text=norm_mark,
                        serial_number=serial,
                        registration_number=(
                            str(item.get("registration_number"))
                            if item.get("registration_number")
                            else None
                        ),
                        status_code=str(item["status_code"]) if item.get("status_code") else None,
                        status_text=str(
                            item.get("status_text") or item.get("status", "REGISTERED")
                        ),
                        is_live=bool(item.get("is_live", True)),
                        classes=list(item.get("classes", [])),
                        goods_services=str(item["goods_services"])
                        if item.get("goods_services")
                        else None,
                        owner_name=(
                            str(item.get("owner_name") or item.get("owner"))
                            if (item.get("owner_name") or item.get("owner"))
                            else None
                        ),
                        filing_date=str(item["filing_date"]) if item.get("filing_date") else None,
                        registration_date=str(item["registration_date"])
                        if item.get("registration_date")
                        else None,
                        source_file=str(item["source_file"]) if item.get("source_file") else None,
                        source_updated_at=item.get("source_updated_at"),
                    )
                    self._session.add(new_rec)
                    inserted += 1
            except Exception:
                failed += 1

        await self._session.flush()
        return {"inserted": inserted, "updated": updated, "failed": failed}
