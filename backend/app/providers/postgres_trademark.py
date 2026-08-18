"""PostgreSQL-backed USPTO Trademark Search Adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.ip_risk import normalize_trademark_phrase
from app.ports.providers import TrademarkMatch, TrademarkSearchPort

if TYPE_CHECKING:
    from app.application.unit_of_work import UnitOfWork


class PostgresTrademarkSearchAdapter(TrademarkSearchPort):
    """Searches official USPTO trademark records stored in PostgreSQL database."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def search_trademark(self, phrase: str) -> list[TrademarkMatch]:
        """Query PostgreSQL trademark database for matching registered marks."""
        norm_phrase = normalize_trademark_phrase(phrase)
        if not norm_phrase or len(norm_phrase) < 2:
            return []

        records = await self._uow.trademarks.search_by_phrase(norm_phrase)
        matches: list[TrademarkMatch] = []
        for r in records:
            source_url = (
                f"https://tsdr.uspto.gov/#caseNumber={r.serial_number}&caseType=SERIAL_NO&searchType=statusSearch"
                if r.serial_number
                else None
            )
            matches.append(
                TrademarkMatch(
                    mark_text=r.mark_text,
                    serial_number=r.serial_number,
                    registration_number=r.registration_number,
                    status=r.status,
                    is_live=r.is_live,
                    classes=list(r.classes or []),
                    goods_services=r.goods_services,
                    owner=r.owner,
                    filing_date=r.filing_date,
                    registration_date=r.registration_date,
                    source_url=source_url,
                )
            )
        return matches
