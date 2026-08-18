"""Tests for USPTO trademark screening and risk classification."""

import pytest

from app.domain.ip_risk import (
    evaluate_trademark_risk,
    extract_searchable_phrases,
)
from app.domain.workflow import RiskLevel
from app.ports.providers import TrademarkMatch
from app.providers.fake import FakeTrademarkSearchAdapter
from app.providers.uspto import UsptoTrademarkAdapter


class TestTrademarkDomain:
    def test_extract_searchable_phrases(self) -> None:
        phrases = extract_searchable_phrases(
            slogan="Stay Wild Moon Child",
            title="Vintage Celestial Moon Child PNG Sublimation",
            keywords=["moon child", "celestial art"],
            tags=["moon child", "vintage moon", "celestial art", "png download"],
        )
        assert "Stay Wild Moon Child" in phrases
        assert "moon child" in phrases
        assert "celestial art" in phrases
        assert "vintage moon" in phrases

    def test_evaluate_risk_cleared_when_no_matches(self) -> None:
        phrases = ["cute mushroom png", "cottagecore frog"]
        matches: list[dict[str, object]] = []

        risk_level, findings = evaluate_trademark_risk(phrases, matches)
        assert risk_level == RiskLevel.LOW
        assert findings["match_count"] == 0
        assert "not legal advice" in findings["disclaimer"].lower()
        assert findings["blocks_approval"] is False
        assert findings["requires_acknowledgement"] is False

    def test_evaluate_risk_cleared_when_only_dead_matches(self) -> None:
        phrases = ["retro sunset graphic"]
        matches = [
            {
                "mark_text": "RETRO SUNSET",
                "status": "CANCELLED",
                "is_live": False,
                "classes": ["025"],
                "goods_services": "Shirts",
            }
        ]

        risk_level, findings = evaluate_trademark_risk(phrases, matches)
        assert risk_level == RiskLevel.LOW
        assert findings["match_count"] == 1
        assert findings["findings"][0]["match_type"] == "DEAD_MARK"

    def test_evaluate_risk_high_when_live_pod_matches(self) -> None:
        phrases = ["disney castle silhouette"]
        matches = [
            {
                "mark_text": "DISNEY",
                "status": "REGISTERED",
                "is_live": True,
                "classes": ["025", "009"],
                "goods_services": "Clothing and downloadable art files",
            }
        ]

        risk_level, findings = evaluate_trademark_risk(phrases, matches)
        assert risk_level == RiskLevel.HIGH
        assert findings["blocks_approval"] is True
        assert any(f["is_live"] for f in findings["findings"])

    def test_evaluate_risk_warning_when_live_non_pod_classes(self) -> None:
        phrases = ["espresso cafe blend"]
        matches = [
            {
                "mark_text": "ESPRESSO CAFE",
                "status": "REGISTERED",
                "is_live": True,
                "classes": ["030", "043"],
                "goods_services": "Coffee and cafe services",
            }
        ]

        risk_level, findings = evaluate_trademark_risk(phrases, matches)
        assert risk_level == RiskLevel.MEDIUM
        assert findings["requires_acknowledgement"] is True
        assert findings["blocks_approval"] is False


class TestTrademarkAdapters:
    @pytest.mark.asyncio
    async def test_fake_adapter_deterministic_triggers(self) -> None:
        adapter = FakeTrademarkSearchAdapter()

        disney_matches = await adapter.search_trademark("Vintage Disney Castle")
        assert len(disney_matches) > 0
        assert disney_matches[0].is_live is True
        assert "025" in disney_matches[0].classes

        warning_matches = await adapter.search_trademark("Coffee Warning Cafe")
        assert len(warning_matches) > 0
        assert "030" in warning_matches[0].classes

        dead_matches = await adapter.search_trademark("Dead Brand Apparel")
        assert len(dead_matches) > 0
        assert dead_matches[0].is_live is False

        clean_matches = await adapter.search_trademark("cottagecore mushroom frog")
        assert len(clean_matches) == 0

    @pytest.mark.asyncio
    async def test_fake_adapter_canned_matches(self) -> None:
        adapter = FakeTrademarkSearchAdapter()
        adapter.set_canned_matches(
            "custom phrase",
            [
                TrademarkMatch(
                    mark_text="CUSTOM PHRASE",
                    status="REGISTERED",
                    is_live=True,
                    classes=["025"],
                )
            ],
        )

        matches = await adapter.search_trademark("Custom Phrase")
        assert len(matches) == 1
        assert matches[0].mark_text == "CUSTOM PHRASE"

    def test_uspto_adapter_response_parsing(self) -> None:
        adapter = UsptoTrademarkAdapter(api_key="test-key")
        raw_json = {
            "cases": [
                {
                    "markLiteralText": "TEST BRAND",
                    "serialNumber": "88123456",
                    "registrationNumber": "5678901",
                    "statusDescriptionText": "REGISTERED",
                    "liveDeadIndicator": "LIVE",
                    "internationalClassCodes": ["025", "009"],
                    "goodsAndServicesDescriptionText": "T-shirts and digital graphic files.",
                    "ownerName": "Test Corp LLC",
                    "filingDate": "2021-01-01",
                    "registrationDate": "2022-01-01",
                }
            ]
        }

        parsed = adapter._parse_uspto_response(raw_json)
        assert len(parsed) == 1
        assert parsed[0].mark_text == "TEST BRAND"
        assert parsed[0].serial_number == "88123456"
        assert parsed[0].is_live is True
        assert parsed[0].classes == ["025", "009"]
        assert parsed[0].owner == "Test Corp LLC"
        assert "tsdr.uspto.gov" in (parsed[0].source_url or "")

    @pytest.mark.asyncio
    async def test_uspto_adapter_http_error_handling(self) -> None:
        import httpx
        from app.ports.errors import ProviderError, ProviderErrorKind

        # 403 Forbidden / Auth failure
        async def mock_handler_403(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"message": "Forbidden"})

        client_403 = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler_403))
        adapter_403 = UsptoTrademarkAdapter(api_key="bad-key", client=client_403)
        with pytest.raises(ProviderError) as exc_info:
            await adapter_403.search_trademark("test query")
        assert exc_info.value.kind == ProviderErrorKind.AUTHENTICATION

        # 429 Rate limited
        async def mock_handler_429(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="Too Many Requests")

        client_429 = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler_429))
        adapter_429 = UsptoTrademarkAdapter(api_key="test-key", client=client_429)
        with pytest.raises(ProviderError) as exc_info:
            await adapter_429.search_trademark("test query")
        assert exc_info.value.kind == ProviderErrorKind.RATE_LIMITED

        # 404 Not found returns empty list
        async def mock_handler_404(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "Not Found"})

        client_404 = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler_404))
        adapter_404 = UsptoTrademarkAdapter(api_key="test-key", client=client_404)
        results = await adapter_404.search_trademark("not found term")
        assert results == []

        # 500 Server error
        async def mock_handler_500(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        client_500 = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler_500))
        adapter_500 = UsptoTrademarkAdapter(api_key="test-key", client=client_500)
        with pytest.raises(ProviderError) as exc_info:
            await adapter_500.search_trademark("test query")
        assert exc_info.value.kind == ProviderErrorKind.RETRYABLE


class TestTrademarkScreeningService:
    @pytest.mark.asyncio
    async def test_screening_service_success_source(self) -> None:
        from app.application.trademark import TrademarkScreeningService

        adapter = FakeTrademarkSearchAdapter()
        service = TrademarkScreeningService(adapter)

        risk, findings = await service.screen_listing_trademark(
            slogan="Cozy Season",
            title="Cozy Season Fall Graphic",
            keywords=["cozy", "autumn"],
            tags=["cozy season", "autumn graphic"],
        )
        assert risk == RiskLevel.LOW
        assert findings["screening_source"] == "USPTO"
        assert findings["uspto_status"] == "SUCCESS"
        assert findings["warning_message"] is None

    @pytest.mark.asyncio
    async def test_screening_service_fallback_when_provider_fails(self) -> None:
        import httpx
        from app.application.trademark import TrademarkScreeningService

        async def mock_handler_fail(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"message": "Unauthorized"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler_fail))
        adapter = UsptoTrademarkAdapter(api_key="unentitled-key", client=client)
        service = TrademarkScreeningService(adapter)

        # Screen an unconflicted phrase with a failing USPTO provider
        risk, findings = await service.screen_listing_trademark(
            slogan="Warm Pumpkin Spice",
            title="Warm Pumpkin Spice Latte PNG",
            keywords=["pumpkin"],
            tags=["pumpkin spice"],
        )
        # Should record local defense registry fallback
        assert findings["screening_source"] == "local_defense_registry"
        assert findings["uspto_status"] == "UNAVAILABLE"
        assert "unavailable" in findings["warning_message"].lower()
        assert risk == RiskLevel.LOW

        # But if the phrase contains a restricted brand, local defense still catches it!
        risk_brand, findings_brand = await service.screen_listing_trademark(
            slogan="Nike Runner",
            title="Nike Runner Digital File",
            keywords=["nike"],
            tags=["nike runner"],
        )
        assert risk_brand == RiskLevel.HIGH
        assert findings_brand["screening_source"] == "local_defense_registry"
        assert findings_brand["blocks_approval"] is True

    @pytest.mark.asyncio
    async def test_screening_service_with_database_fallback(self) -> None:
        from unittest.mock import AsyncMock, MagicMock
        from app.application.trademark import TrademarkScreeningService
        from app.ports.providers import TrademarkMatch
        from app.providers.postgres_trademark import PostgresTrademarkSearchAdapter

        # Mock UoW and Trademark Repository
        mock_uow = MagicMock()
        mock_rec = MagicMock()
        mock_rec.mark_text = "COFFEE BEFORE PEOPLE"
        mock_rec.serial_number = "88999111"
        mock_rec.registration_number = "6111222"
        mock_rec.status = "REGISTERED"
        mock_rec.is_live = True
        mock_rec.classes = ["025"]
        mock_rec.goods_services = "T-shirts and hoodies"
        mock_rec.owner = "Coffee Lovers LLC"
        mock_rec.filing_date = "2020-01-01"
        mock_rec.registration_date = "2021-01-01"

        mock_uow.trademarks.search_by_phrase = AsyncMock(return_value=[mock_rec])
        db_adapter = PostgresTrademarkSearchAdapter(mock_uow)

        # Primary provider fails (e.g. 403 on live USPTO)
        failing_provider = MagicMock()
        failing_provider.search_trademark = AsyncMock(side_effect=Exception("HTTP 403 Forbidden"))

        service = TrademarkScreeningService(
            trademark_provider=failing_provider,
            fallback_provider=db_adapter,
        )

        risk, findings = await service.screen_listing_trademark(
            slogan="Coffee Before People",
            title="Coffee Before People Graphic Tee PNG",
            keywords=["coffee"],
            tags=["coffee lover"],
        )

        assert risk == RiskLevel.HIGH
        assert findings["screening_source"] == "local_defense_registry"
        assert findings["uspto_status"] == "UNAVAILABLE"
        assert len(findings["matches"]) >= 1
        assert findings["matches"][0]["mark_text"] == "COFFEE BEFORE PEOPLE"
        assert findings["matches"][0]["serial_number"] == "88999111"
        assert "tsdr.uspto.gov" in findings["matches"][0]["source_url"]

