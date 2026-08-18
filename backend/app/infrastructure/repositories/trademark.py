"""SQLAlchemy repository for TrademarkRecord entities."""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import or_, select
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

    async def search_by_phrase(self, phrase: str, limit: int = 25) -> list[TrademarkRecord]:
        """Search trademark records for a phrase (exact, substring, or token match)."""
        norm_phrase = normalize_trademark_phrase(phrase)
        if not norm_phrase or len(norm_phrase) < 2:
            return []

        # 1. Exact normalized match
        # 2. Substring matching in norm_mark_text or raw mark_text
        stmt = (
            select(TrademarkRecord)
            .where(
                or_(
                    TrademarkRecord.norm_mark_text == norm_phrase,
                    TrademarkRecord.norm_mark_text.ilike(f"%{norm_phrase}%"),
                    TrademarkRecord.mark_text.ilike(f"%{phrase.strip()}%"),
                )
            )
            .order_by(
                TrademarkRecord.is_live.desc(),
                (TrademarkRecord.norm_mark_text == norm_phrase).desc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> int:
        """Insert or update trademark records."""
        count = 0
        for item in records:
            mark_text = str(item.get("mark_text", "")).strip()
            if not mark_text:
                continue
            norm_mark = normalize_trademark_phrase(mark_text)
            serial = str(item.get("serial_number")) if item.get("serial_number") else None

            existing: TrademarkRecord | None = None
            if serial:
                existing = await self.get_by_serial(serial)

            if existing is None:
                stmt = select(TrademarkRecord).where(TrademarkRecord.norm_mark_text == norm_mark)
                res = await self._session.execute(stmt)
                existing = res.scalars().first()

            if existing:
                existing.mark_text = mark_text
                existing.norm_mark_text = norm_mark
                existing.status = item.get("status", existing.status)
                existing.is_live = bool(item.get("is_live", existing.is_live))
                existing.classes = item.get("classes", existing.classes)
                existing.goods_services = item.get("goods_services", existing.goods_services)
                existing.owner = item.get("owner", existing.owner)
                existing.filing_date = item.get("filing_date", existing.filing_date)
                existing.registration_date = item.get("registration_date", existing.registration_date)
                existing.source = item.get("source", existing.source)
            else:
                new_rec = TrademarkRecord(
                    id=uuid.uuid4(),
                    mark_text=mark_text,
                    norm_mark_text=norm_mark,
                    serial_number=serial,
                    registration_number=str(item.get("registration_number")) if item.get("registration_number") else None,
                    status=item.get("status", "REGISTERED"),
                    is_live=bool(item.get("is_live", True)),
                    classes=item.get("classes", []),
                    goods_services=item.get("goods_services"),
                    owner=item.get("owner"),
                    filing_date=item.get("filing_date"),
                    registration_date=item.get("registration_date"),
                    source=item.get("source", "USPTO_BULK"),
                )
                self._session.add(new_rec)
            count += 1

        await self._session.flush()
        return count
