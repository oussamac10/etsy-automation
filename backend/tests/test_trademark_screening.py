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
