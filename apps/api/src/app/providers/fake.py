"""Deterministic fake providers.

These are the default in ``local`` and the only implementations available in
Phase 1. They are seeded by their inputs so tests and demos are reproducible,
and none of them performs network I/O or costs money.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import (
    CostEstimate,
    ImageRequest,
    ImageResponse,
    SearchQuery,
    SearchResult,
    StoredObject,
    TextRequest,
    TextResponse,
    TrademarkSignal,
)

FAKE_PROVIDER_NAME = "fake"

# A 1x1 transparent PNG. Original, minimal, and obviously not real artwork.
_TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff03000006"
    "000557bfabd40000000049454e44ae426082"
)


def _seed(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class FixedClock:
    """A clock that never moves. Injected wherever determinism matters."""

    def __init__(self, moment: datetime | None = None) -> None:
        self._moment = moment or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._moment


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeResearchProvider:
    """Returns clearly-labelled placeholder evidence.

    It never fabricates a number: no search volume, sales or revenue figure
    appears in the output, because inventing one is forbidden by CLAUDE.md.
    """

    name = FAKE_PROVIDER_NAME

    def __init__(self, clock: SystemClock | FixedClock | None = None) -> None:
        self._clock = clock or FixedClock()

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        captured = self._clock.now()
        return [
            SearchResult(
                url=f"https://example.invalid/fake-evidence/{_seed(query.text, str(index))[:12]}",
                title=f"Fake evidence {index + 1} for angle '{query.angle}'",
                observation=(
                    "Placeholder observation produced by the fake research provider. "
                    "It contains no market data and must not be used for a decision."
                ),
                source_type="fake",
                captured_at=captured,
            )
            for index in range(3)
        ]


class FakeTextProvider:
    name = FAKE_PROVIDER_NAME

    async def generate(self, request: TextRequest) -> TextResponse:
        digest = _seed(request.prompt)
        return TextResponse(
            text=f"[fake-text:{digest[:12]}] deterministic placeholder response",
            input_tokens=len(request.prompt.split()),
            output_tokens=8,
            model="fake-text-1",
        )


class FakeImageProvider:
    """Returns a transparent 1x1 PNG and records the idempotency key it saw."""

    name = FAKE_PROVIDER_NAME

    def __init__(self) -> None:
        self.seen_idempotency_keys: list[str] = []

    async def generate(self, request: ImageRequest) -> ImageResponse:
        if not request.idempotency_key:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=FAKE_PROVIDER_NAME,
                operation="image_generation",
                message="idempotency_key is required for every paid operation",
            )
        self.seen_idempotency_keys.append(request.idempotency_key)
        return ImageResponse(
            image_bytes=_TRANSPARENT_PNG,
            mime_type="image/png",
            model="fake-image-1",
            provider_request_id=_seed(request.idempotency_key)[:16],
        )


class InMemoryObjectStorage:
    """Storage adapter for tests and local runs. Keys are opaque, never paths."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self._objects[key] = (data, content_type)
        return StoredObject(
            storage_key=key,
            sha256=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            content_type=content_type,
        )

    async def get(self, key: str) -> bytes:
        try:
            return self._objects[key][0]
        except KeyError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=FAKE_PROVIDER_NAME,
                operation="storage_get",
                message="object not found",
            ) from exc

    async def signed_url(self, key: str, expires_in_seconds: int) -> str:
        return f"memory://{key}?expires_in={expires_in_seconds}"


class FakeTrademarkGateway:
    """Always returns ``unknown`` risk with an explicit disclaimer.

    A fake source can never lower risk, so it must not be able to make a phrase
    look clear.
    """

    async def lookup(self, phrase: str) -> list[TrademarkSignal]:
        return [
            TrademarkSignal(
                phrase=phrase,
                source="fake",
                observed=(
                    "No trademark database was queried. This is a placeholder "
                    "result and is not a clearance search."
                ),
                risk="unknown",
            )
        ]


class ZeroCostCalculator:
    """Fake providers cost nothing, but still produce a ledger entry."""

    def estimate(self, provider: str, operation: str, units: dict[str, int]) -> CostEstimate:
        return CostEstimate(
            amount_usd=Decimal("0.00"),
            breakdown={
                "provider": provider,
                "operation": operation,
                **{key: str(value) for key, value in units.items()},
            },
        )
