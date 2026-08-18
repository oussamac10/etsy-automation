"""Tests for USPTO trademark screening, database search, bulk ingestion, and TSDR verification."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

from app.domain.ip_risk import (
    evaluate_trademark_risk,
    extract_searchable_phrases,
    normalize_trademark_phrase,
)
from app.domain.workflow import RiskLevel
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import TrademarkMatch
from app.providers.fake import FakeTrademarkSearchAdapter
from app.providers.postgres_trademark import PostgresTrademarkSearchAdapter
from app.providers.tsdr import UsptoTsdrAdapter
from app.providers.uspto import UsptoTrademarkAdapter
from app.application.trademark import TrademarkScreeningService


class TestTrademarkDomain:
    def test_normalize_trademark_phrase(self) -> None:
        assert normalize_trademark_phrase("  NiKe,  Runner!  ") == "nike runner"
        assert normalize_trademark_phrase("Coffee... Before    People???") == "coffee before people"
        assert normalize_trademark_phrase("Boy-Mama / Girl_Mama") == "boymama girl_mama"

    def test_extract_searchable_phrases_deduplication(self) -> None:
        phrases = extract_searchable_phrases(
            slogan="Stay Wild Moon Child",
            title="Vintage Celestial Moon Child PNG | Sublimation Design",
            keywords=["moon child", "celestial art", "moon child"],
            tags=["moon child", "vintage moon", "celestial art", "png download", "and", "the"],
        )
        assert "Stay Wild Moon Child" in phrases
        assert "moon child" in phrases
        assert "celestial art" in phrases
        assert "vintage moon" in phrases
        # Stopwords and duplicate occurrences are filtered
        assert "and" not in phrases
        assert "the" not in phrases

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


class TestTsdrAdapter:
    @pytest.mark.asyncio
    async def test_tsdr_adapter_success(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            data = {
                "caseHeader": {
                    "markLiteralText": "TEST NIKE",
                    "statusDesc": "REGISTERED",
                    "liveDeadIndicator": "LIVE",
                },
                "internationalClassList": [{"classCode": "025"}, {"classCode": "009"}],
                "goodsAndServicesList": [{"description": "Footwear and athletic apparel"}],
                "ownerList": [{"partyName": "Nike, Inc."}],
            }
            return httpx.Response(200, json=data)

        client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = UsptoTsdrAdapter(api_key="valid-key", client=client)

        result = await adapter.verify_serial_number("73000001")
        assert result is not None
        assert result["mark_text"] == "TEST NIKE"
        assert result["is_live"] is True
        assert result["classes"] == ["025", "009"]
        assert result["owner"] == "Nike, Inc."
        assert result["tsdr_verified"] is True

    @pytest.mark.asyncio
    async def test_tsdr_adapter_auth_error_403(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"message": "Forbidden"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = UsptoTsdrAdapter(api_key="bad-key", client=client)

        with pytest.raises(ProviderError) as exc_info:
            await adapter.verify_serial_number("73000001")
        assert exc_info.value.kind == ProviderErrorKind.AUTHENTICATION

    @pytest.mark.asyncio
    async def test_tsdr_adapter_rate_limit_429(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="Rate limit exceeded")

        client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = UsptoTsdrAdapter(api_key="key", client=client)

        with pytest.raises(ProviderError) as exc_info:
            await adapter.verify_serial_number("73000001")
        assert exc_info.value.kind == ProviderErrorKind.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_tsdr_adapter_timeout(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Timeout connecting to TSDR")

        client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = UsptoTsdrAdapter(api_key="key", client=client)

        with pytest.raises(ProviderError) as exc_info:
            await adapter.verify_serial_number("73000001")
        assert exc_info.value.kind == ProviderErrorKind.RETRYABLE


class TestPostgresTrademarkAdapter:
    @pytest.mark.asyncio
    async def test_postgres_trademark_search_adapter_mapping(self) -> None:
        mock_uow = MagicMock()
        mock_rec = MagicMock()
        mock_rec.mark_text = "NIKE"
        mock_rec.serial_number = "73000001"
        mock_rec.registration_number = "1234567"
        mock_rec.status_text = "REGISTERED"
        mock_rec.is_live = True
        mock_rec.classes = ["025", "009"]
        mock_rec.goods_services = "Athletic apparel"
        mock_rec.owner_name = "Nike, Inc."
        mock_rec.filing_date = "1971-01-01"
        mock_rec.registration_date = "1974-01-01"

        mock_uow.trademarks.search_by_phrase = AsyncMock(return_value=[mock_rec])
        adapter = PostgresTrademarkSearchAdapter(mock_uow)

        matches = await adapter.search_trademark("Nike Runner")
        assert len(matches) == 1
        assert matches[0].mark_text == "NIKE"
        assert matches[0].serial_number == "73000001"
        assert matches[0].is_live is True
        assert matches[0].classes == ["025", "009"]
        assert "caseSearchType=US_APPLICATION" in (matches[0].source_url or "")


class TestTrademarkScreeningService:
    @pytest.mark.asyncio
    async def test_screening_with_tsdr_verification(self) -> None:
        mock_uow = MagicMock()
        mock_rec = MagicMock()
        mock_rec.mark_text = "COFFEE BEFORE PEOPLE"
        mock_rec.serial_number = "88999111"
        mock_rec.registration_number = "6111222"
        mock_rec.status_text = "REGISTERED"
        mock_rec.is_live = True
        mock_rec.classes = ["025"]
        mock_rec.goods_services = "T-shirts and sweatshirts"
        mock_rec.owner_name = "Coffee Lovers LLC"
        mock_rec.filing_date = "2020-01-01"
        mock_rec.registration_date = "2021-01-01"

        mock_uow.trademarks.search_by_phrase = AsyncMock(return_value=[mock_rec])
        db_adapter = PostgresTrademarkSearchAdapter(mock_uow)

        mock_tsdr = MagicMock()
        mock_tsdr.verify_serial_number = AsyncMock(
            return_value={
                "serial_number": "88999111",
                "mark_text": "COFFEE BEFORE PEOPLE",
                "status": "REGISTERED",
                "is_live": True,
                "classes": ["025"],
                "goods_services": "T-shirts, hoodies, and apparel",
                "owner": "Coffee Lovers LLC",
                "tsdr_verified": True,
            }
        )

        service = TrademarkScreeningService(
            trademark_provider=db_adapter,
            tsdr_adapter=mock_tsdr,
            dataset_updated_at="2026-08-18T00:00:00Z",
        )

        risk, findings = await service.screen_listing_trademark(
            slogan="Coffee Before People",
            title="Coffee Before People Fall Graphic PNG",
            keywords=["coffee"],
            tags=["coffee lover", "coffee before people"],
        )

        assert risk == RiskLevel.HIGH
        assert findings["screening_source"] == "USPTO_LOCAL_INDEX_TSDR_VERIFIED"
        assert findings["tsdr_status"] == "VERIFIED"
        assert findings["dataset_updated_at"] == "2026-08-18T00:00:00Z"
        assert findings["blocks_approval"] is True
        assert len(findings["matches"]) >= 1
        assert findings["matches"][0]["tsdr_verified"] is True

    @pytest.mark.asyncio
    async def test_screening_with_tsdr_unavailable_keeps_local_result(self) -> None:
        mock_uow = MagicMock()
        mock_rec = MagicMock()
        mock_rec.mark_text = "STAY WILD"
        mock_rec.serial_number = "88777666"
        mock_rec.registration_number = "5999888"
        mock_rec.status_text = "REGISTERED"
        mock_rec.is_live = True
        mock_rec.classes = ["025"]
        mock_rec.goods_services = "Outdoor apparel"
        mock_rec.owner_name = "Wild Outdoors Co."
        mock_rec.filing_date = "2019-01-01"
        mock_rec.registration_date = "2020-01-01"

        mock_uow.trademarks.search_by_phrase = AsyncMock(return_value=[mock_rec])
        db_adapter = PostgresTrademarkSearchAdapter(mock_uow)

        mock_tsdr = MagicMock()
        mock_tsdr.verify_serial_number = AsyncMock(
            side_effect=ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="tsdr",
                operation="verify_serial_number",
                message="HTTP 403 Forbidden",
            )
        )

        service = TrademarkScreeningService(
            trademark_provider=db_adapter,
            tsdr_adapter=mock_tsdr,
            dataset_updated_at="2026-08-18T00:00:00Z",
        )

        risk, findings = await service.screen_listing_trademark(
            slogan="Stay Wild",
            title="Stay Wild Moon Child PNG",
            keywords=["stay wild"],
            tags=["stay wild"],
        )

        assert risk == RiskLevel.HIGH
        assert findings["screening_source"] == "USPTO_LOCAL_INDEX_TSDR_UNAVAILABLE"
        assert findings["tsdr_status"] == "UNAVAILABLE"
        assert len(findings["matches"]) >= 1
        assert findings["matches"][0]["mark_text"] == "STAY WILD"


class TestBulkIngestionParsers:
    def test_xml_streaming_parser(self) -> None:
        import sys
        backend_dir = str(Path(__file__).resolve().parent.parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from scripts.ingest_uspto_trademarks import _parse_xml_trademark_stream

        xml_sample = """<?xml version="1.0" encoding="UTF-8"?>
        <TrademarkBag>
            <Trademark>
                <Wordmark>TEST RUNNER</Wordmark>
                <SerialNumber>90123456</SerialNumber>
                <RegistrationNumber>6543210</RegistrationNumber>
                <LiveDeadIndicator>LIVE</LiveDeadIndicator>
                <StatusCode>700</StatusCode>
                <StatusDescriptionText>REGISTERED</StatusDescriptionText>
                <InternationalClassNumber>025</InternationalClassNumber>
                <GoodsAndServicesDescription>Running shoes and shirts</GoodsAndServicesDescription>
                <PartyName>Test Athletics LLC</PartyName>
                <FilingDate>2021-05-01</FilingDate>
                <RegistrationDate>2022-06-01</RegistrationDate>
            </Trademark>
        </TrademarkBag>
        """
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
            f.write(xml_sample)
            temp_path = Path(f.name)

        try:
            records = list(_parse_xml_trademark_stream(temp_path))
            assert len(records) == 1
            assert records[0]["mark_text"] == "TEST RUNNER"
            assert records[0]["serial_number"] == "90123456"
            assert records[0]["is_live"] is True
            assert records[0]["classes"] == ["025"]
            assert records[0]["owner_name"] == "Test Athletics LLC"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_csv_streaming_parser(self) -> None:
        import sys
        backend_dir = str(Path(__file__).resolve().parent.parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from scripts.ingest_uspto_trademarks import _parse_csv_trademark_stream

        csv_sample = (
            "mark_text,serial_number,registration_number,status_text,is_live,classes,goods_services,owner_name\n"
            "COFFEE HERO,90999888,6777888,REGISTERED,LIVE,\"025, 021\",Mugs and shirts,Coffee Corp\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(csv_sample)
            temp_path = Path(f.name)

        try:
            records = list(_parse_csv_trademark_stream(temp_path))
            assert len(records) == 1
            assert records[0]["mark_text"] == "COFFEE HERO"
            assert records[0]["serial_number"] == "90999888"
            assert records[0]["classes"] == ["025", "021"]
            assert records[0]["is_live"] is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_json_streaming_parser(self) -> None:
        import sys
        backend_dir = str(Path(__file__).resolve().parent.parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from scripts.ingest_uspto_trademarks import _parse_json_trademark_stream

        json_sample = [
            {
                "mark_text": "MAMA BEAR",
                "serial_number": "87654321",
                "registration_number": "5432109",
                "status_text": "REGISTERED",
                "is_live": True,
                "classes": ["025", "016"],
                "goods_services": "Apparel and stickers",
                "owner_name": "Family Brands LLC",
            }
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(json_sample, f)
            temp_path = Path(f.name)

        try:
            records = list(_parse_json_trademark_stream(temp_path))
            assert len(records) == 1
            assert records[0]["mark_text"] == "MAMA BEAR"
            assert records[0]["serial_number"] == "87654321"
            assert records[0]["classes"] == ["025", "016"]
        finally:
            temp_path.unlink(missing_ok=True)


class TestSqlTrademarkRepository:
    @pytest.mark.asyncio
    async def test_repository_get_by_serial_and_registration(self) -> None:
        from app.infrastructure.repositories.trademark import SqlTrademarkRepository

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_rec = MagicMock()
        mock_rec.serial_number = "90111222"
        mock_rec.registration_number = "6555444"
        mock_result.scalars.return_value.first.return_value = mock_rec
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SqlTrademarkRepository(mock_session)
        rec_serial = await repo.get_by_serial("90111222")
        assert rec_serial is not None
        assert rec_serial.serial_number == "90111222"

        rec_reg = await repo.get_by_registration("6555444")
        assert rec_reg is not None
        assert rec_reg.registration_number == "6555444"

    @pytest.mark.asyncio
    async def test_repository_bulk_upsert(self) -> None:
        from app.infrastructure.repositories.trademark import SqlTrademarkRepository

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        repo = SqlTrademarkRepository(mock_session)
        counts = await repo.bulk_upsert(
            [
                {
                    "mark_text": "NIKE RUNNER",
                    "serial_number": "90111222",
                    "classes": ["025"],
                    "is_live": True,
                },
                {
                    "mark_text": "COFFEE HERO",
                    "serial_number": "90333444",
                    "classes": ["021"],
                    "is_live": True,
                },
            ]
        )
        assert counts["inserted"] == 2
        assert counts["updated"] == 0
        assert counts["failed"] == 0
        assert mock_session.add.call_count == 2

