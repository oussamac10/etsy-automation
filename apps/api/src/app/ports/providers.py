"""Provider interfaces.

Phase 1 defines the boundary only. Real adapters arrive in the phases that own
them (research/text: Phase 4, images: Phase 5, Etsy: Phase 8). Every method
below is expected to raise :class:`app.ports.errors.ProviderError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

# --------------------------------------------------------------------------
# Value objects crossing the port boundary. Deliberately plain: no provider
# SDK type may appear in a signature.
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchQuery:
    text: str
    #: Buyer-intent angle this query represents (broad, long-tail, occasion, ...).
    angle: str
    country: str = "US"
    language: str = "en"


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One piece of evidence. ``observation`` is what the source states."""

    url: str
    title: str
    observation: str
    source_type: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class TextRequest:
    prompt: str
    system: str | None = None
    max_output_tokens: int = 2048


@dataclass(frozen=True, slots=True)
class TextResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


@dataclass(frozen=True, slots=True)
class ImageRequest:
    positive_prompt: str
    negative_prompt: str
    width: int
    height: int
    quality: str
    #: Stable key so a duplicate dispatch is billed once.
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ImageResponse:
    image_bytes: bytes
    mime_type: str
    model: str
    provider_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Money is Decimal, never float (packages/domain/CLAUDE.md)."""

    amount_usd: Decimal
    currency: str = "USD"
    breakdown: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoredObject:
    storage_key: str
    sha256: str
    byte_size: int
    content_type: str


@dataclass(frozen=True, slots=True)
class TrademarkSignal:
    """A *preliminary* signal only. It never concludes that a phrase is free."""

    phrase: str
    source: str
    observed: str
    risk: str


# --------------------------------------------------------------------------
# Ports
# --------------------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    """Injected so the domain stays deterministic under test."""

    def now(self) -> datetime: ...


@runtime_checkable
class ResearchProvider(Protocol):
    async def search(self, query: SearchQuery) -> list[SearchResult]: ...


@runtime_checkable
class TextGenerationProvider(Protocol):
    async def generate(self, request: TextRequest) -> TextResponse: ...


@runtime_checkable
class ImageGenerationProvider(Protocol):
    name: str

    async def generate(self, request: ImageRequest) -> ImageResponse: ...


@runtime_checkable
class ImageProcessingProvider(Protocol):
    async def remove_background(self, image: bytes) -> bytes: ...

    async def upscale(self, image: bytes, factor: int) -> bytes: ...


@runtime_checkable
class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...

    async def get(self, key: str) -> bytes: ...

    async def signed_url(self, key: str, expires_in_seconds: int) -> str: ...


@runtime_checkable
class EtsyGateway(Protocol):
    """Creates drafts. There is intentionally no publish/activate method."""

    async def create_draft_listing(
        self, shop_id: str, payload: dict[str, object], idempotency_key: str
    ) -> str: ...

    async def upload_listing_image(
        self, shop_id: str, listing_id: str, image: bytes, idempotency_key: str
    ) -> str: ...


@runtime_checkable
class TrademarkDataGateway(Protocol):
    async def lookup(self, phrase: str) -> list[TrademarkSignal]: ...


@runtime_checkable
class CostCalculator(Protocol):
    def estimate(self, provider: str, operation: str, units: dict[str, int]) -> CostEstimate: ...
