"""Application service for USPTO trademark search and IP risk classification."""

from __future__ import annotations

from typing import Any
import structlog

from app.domain.ip_risk import evaluate_trademark_risk, extract_searchable_phrases
from app.domain.workflow import RiskLevel
from app.ports.providers import TrademarkMatch, TrademarkSearchPort

logger = structlog.get_logger(__name__)


class TrademarkScreeningService:
    """Coordinates trademark phrase extraction, USPTO querying, and risk classification."""

    def __init__(
        self,
        trademark_provider: TrademarkSearchPort,
        fallback_provider: TrademarkSearchPort | None = None,
    ) -> None:
        self._provider = trademark_provider
        self._fallback_provider = fallback_provider

    async def screen_listing_trademark(
        self,
        slogan: str | None,
        title: str | None,
        keywords: list[str] | None,
        tags: list[str] | None,
    ) -> tuple[RiskLevel, dict[str, Any]]:
        """Screen listing terms against the trademark provider and classify risk."""
        phrases = extract_searchable_phrases(slogan, title, keywords, tags)
        logger.info("screening_trademarks", phrases_count=len(phrases), phrases=phrases)

        all_matches: list[dict[str, Any]] = []
        uspto_failed = False
        uspto_failure_reason: str | None = None

        # Query primary provider for each unique phrase (deduplicated)
        for phrase in phrases:
            try:
                matches: list[TrademarkMatch] = await self._provider.search_trademark(phrase)
                for m in matches:
                    all_matches.append(
                        {
                            "mark_text": m.mark_text,
                            "serial_number": m.serial_number,
                            "registration_number": m.registration_number,
                            "status": m.status,
                            "is_live": m.is_live,
                            "goods_services": m.goods_services,
                            "classes": m.classes,
                            "owner": m.owner,
                            "filing_date": m.filing_date,
                            "registration_date": m.registration_date,
                            "source_url": m.source_url,
                        }
                    )
            except Exception as exc:
                logger.warning("trademark_query_failed", phrase=phrase, error=str(exc))
                uspto_failed = True
                uspto_failure_reason = str(exc)
                if self._fallback_provider:
                    try:
                        fallback_matches = await self._fallback_provider.search_trademark(phrase)
                        for m in fallback_matches:
                            all_matches.append(
                                {
                                    "mark_text": m.mark_text,
                                    "serial_number": m.serial_number,
                                    "registration_number": m.registration_number,
                                    "status": m.status,
                                    "is_live": m.is_live,
                                    "goods_services": m.goods_services,
                                    "classes": m.classes,
                                    "owner": m.owner,
                                    "filing_date": m.filing_date,
                                    "registration_date": m.registration_date,
                                    "source_url": m.source_url,
                                }
                            )
                    except Exception as fb_exc:
                        logger.warning("fallback_query_failed", phrase=phrase, error=str(fb_exc))

        if uspto_failed:
            screening_source = "local_defense_registry"
            uspto_status = "UNAVAILABLE"
            warning_message = (
                "USPTO live API was unavailable. Results below are verified against the local "
                "USPTO database and preliminary defense screen."
            )
        else:
            screening_source = "USPTO"
            uspto_status = "SUCCESS"
            warning_message = None

        # Evaluate risk deterministically using pure domain rules
        risk_level, findings = evaluate_trademark_risk(
            searched_phrases=phrases,
            matches=all_matches,
            screening_source=screening_source,
            uspto_status=uspto_status,
            warning_message=warning_message,
        )

        logger.info(
            "trademark_screening_complete",
            risk_level=risk_level.value,
            screening_source=screening_source,
            matches_count=len(all_matches),
        )
        return risk_level, findings
