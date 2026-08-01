"""Contract tests for the Phase 1 fake adapters.

They double as a guard on the promises in CLAUDE.md: fakes must be
deterministic, must not invent market numbers, and must not make a phrase look
cleared.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import (
    ImageGenerationProvider,
    ImageRequest,
    ObjectStorage,
    ResearchProvider,
    SearchQuery,
    TextGenerationProvider,
    TextRequest,
    TrademarkDataGateway,
)
from app.providers.fake import (
    FakeImageProvider,
    FakeResearchProvider,
    FakeTextProvider,
    FakeTrademarkGateway,
    FixedClock,
    InMemoryObjectStorage,
    ZeroCostCalculator,
)

NUMBER_LIKE = re.compile(r"\b\d[\d,.]*\s*(sales|searches|revenue|orders|per month|/mo)\b", re.I)


def test_fakes_satisfy_their_ports() -> None:
    assert isinstance(FakeResearchProvider(), ResearchProvider)
    assert isinstance(FakeTextProvider(), TextGenerationProvider)
    assert isinstance(FakeImageProvider(), ImageGenerationProvider)
    assert isinstance(InMemoryObjectStorage(), ObjectStorage)
    assert isinstance(FakeTrademarkGateway(), TrademarkDataGateway)


async def test_research_provider_is_deterministic() -> None:
    provider = FakeResearchProvider(clock=FixedClock())
    query = SearchQuery(text="boho sunflower png", angle="long-tail")
    first = await provider.search(query)
    second = await provider.search(query)
    assert first == second


async def test_research_provider_invents_no_market_numbers() -> None:
    results = await FakeResearchProvider().search(SearchQuery(text="sunflower", angle="broad"))
    for result in results:
        assert not NUMBER_LIKE.search(result.observation)
        assert result.source_type == "fake"


async def test_research_evidence_is_labelled_as_placeholder() -> None:
    results = await FakeResearchProvider().search(SearchQuery(text="x", angle="broad"))
    assert all("placeholder" in r.observation.lower() for r in results)


async def test_text_provider_is_deterministic() -> None:
    provider = FakeTextProvider()
    request = TextRequest(prompt="describe a concept")
    assert (await provider.generate(request)).text == (await provider.generate(request)).text


async def test_image_provider_returns_a_transparent_png() -> None:
    response = await FakeImageProvider().generate(
        ImageRequest(
            positive_prompt="p",
            negative_prompt="n",
            width=1024,
            height=1536,
            quality="medium",
            idempotency_key="run-1:image:abc",
        )
    )
    assert response.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.mime_type == "image/png"


async def test_image_provider_requires_an_idempotency_key() -> None:
    with pytest.raises(ProviderError) as excinfo:
        await FakeImageProvider().generate(
            ImageRequest(
                positive_prompt="p",
                negative_prompt="n",
                width=1024,
                height=1024,
                quality="medium",
                idempotency_key="",
            )
        )
    assert excinfo.value.kind is ProviderErrorKind.INVALID_REQUEST
    assert excinfo.value.is_retryable is False


async def test_storage_roundtrip_records_a_hash() -> None:
    storage = InMemoryObjectStorage()
    stored = await storage.put("assets/a.png", b"bytes", "image/png")
    assert len(stored.sha256) == 64
    assert await storage.get("assets/a.png") == b"bytes"


async def test_storage_signed_url_carries_an_expiry() -> None:
    url = await InMemoryObjectStorage().signed_url("assets/a.png", 300)
    assert "expires_in=300" in url


async def test_trademark_gateway_never_reports_low_risk() -> None:
    signals = await FakeTrademarkGateway().lookup("live laugh love")
    assert [signal.risk for signal in signals] == ["unknown"]
    assert "not a clearance search" in signals[0].observed


def test_zero_cost_calculator_uses_decimal() -> None:
    estimate = ZeroCostCalculator().estimate("fake", "image_generation", {"images": 1})
    assert estimate.amount_usd == Decimal("0.00")
    assert isinstance(estimate.amount_usd, Decimal)


def test_provider_error_retry_classification() -> None:
    retryable = ProviderError(
        kind=ProviderErrorKind.RATE_LIMITED,
        provider="fake",
        operation="op",
        message="slow down",
        retry_after_seconds=2.0,
    )
    permanent = ProviderError(
        kind=ProviderErrorKind.INVALID_REQUEST,
        provider="fake",
        operation="op",
        message="bad request",
    )
    assert retryable.is_retryable is True
    assert permanent.is_retryable is False
