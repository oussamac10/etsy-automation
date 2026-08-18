"""Application service for USPTO trademark search and IP risk classification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import structlog

from app.domain.ip_risk import evaluate_trademark_risk, extract_searchable_phrases
from app.domain.workflow import RiskLevel
from app.ports.providers import TrademarkMatch, TrademarkSearchPort

logger = structlog.get_logger(__name__)


class TrademarkScreeningService:
    """Coordinates trademark phrase extraction, USPTO querying, TSDR verification, and risk classification."""

    def __init__(
        self,
        trademark_provider: TrademarkSearchPort,
        fallback_provider: TrademarkSearchPort | None = None,
        tsdr_adapter: Any | None = None,
        dataset_updated_at: str | None = None,
    ) -> None:
        self._provider = trademark_provider
        self._fallback_provider = fallback_provider
        self._tsdr_adapter = tsdr_adapter
        self._dataset_updated_at = dataset_updated_at

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

        tsdr_status = "NOT_QUERIED"
        tsdr_verified_at: str | None = None

        # TSDR candidate verification when serial number exists and tsdr_adapter is configured
        if self._tsdr_adapter and all_matches:
            for match in all_matches[:5]:  # Bounded verification on candidate matches
                serial = match.get("serial_number")
                if serial:
                    try:
                        tsdr_data = await self._tsdr_adapter.verify_serial_number(serial)
                        if tsdr_data:
                            match["status"] = tsdr_data.get("status", match["status"])
                            match["is_live"] = tsdr_data.get("is_live", match["is_live"])
                            if tsdr_data.get("classes"):
                                match["classes"] = tsdr_data["classes"]
                            if tsdr_data.get("goods_services"):
                                match["goods_services"] = tsdr_data["goods_services"]
                            if tsdr_data.get("owner"):
                                match["owner"] = tsdr_data["owner"]
                            match["tsdr_verified"] = True
                            tsdr_status = "VERIFIED"
                            tsdr_verified_at = datetime.now(timezone.utc).isoformat()
                    except Exception as tsdr_exc:
                        logger.warning("tsdr_candidate_verification_failed", serial=serial, error=str(tsdr_exc))
                        tsdr_status = "UNAVAILABLE"

        if uspto_failed:
            screening_source = "local_defense_registry"
            uspto_status = "UNAVAILABLE"
            warning_message = (
                "USPTO screening was unavailable. Results below are from the local "
                "preliminary defense screen only."
            )
        else:
            if tsdr_status == "VERIFIED":
                screening_source = "USPTO_LOCAL_INDEX_TSDR_VERIFIED"
            elif tsdr_status == "UNAVAILABLE":
                screening_source = "USPTO_LOCAL_INDEX_TSDR_UNAVAILABLE"
            else:
                screening_source = "USPTO_LOCAL_INDEX"

            uspto_status = "SUCCESS"
            warning_message = None

        # Evaluate risk deterministically using pure domain rules
        risk_level, findings = evaluate_trademark_risk(
            searched_phrases=phrases,
            matches=all_matches,
            screening_source=screening_source,
            uspto_status=uspto_status,
            warning_message=warning_message,
            dataset_updated_at=self._dataset_updated_at,
            tsdr_status=tsdr_status,
            tsdr_verified_at=tsdr_verified_at,
        )

        logger.info(
            "trademark_screening_complete",
            risk_level=risk_level.value,
            screening_source=screening_source,
            matches_count=len(all_matches),
            tsdr_status=tsdr_status,
        )
        return risk_level, findings

    async def screen_concept_trademark(
        self,
        slogan: str | None,
        title: str | None,
        description: str | None = None,
    ) -> tuple[RiskLevel, dict[str, Any]]:
        """Screen a proposed product concept's slogan and title early in Phase 1."""
        return await self.screen_listing_trademark(
            slogan=slogan,
            title=title,
            keywords=[title] if title else None,
            tags=None,
        )

