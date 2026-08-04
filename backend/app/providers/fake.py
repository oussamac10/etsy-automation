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
        import json
        import re

        prompt_lower = request.prompt.lower()
        is_user_or_hybrid = "original idea" in prompt_lower or "user idea" in prompt_lower

        original_text = "Sleepy Fox curling around a mug"
        if is_user_or_hybrid:
            match = re.search(r"original idea:\s*([^\n]+)", request.prompt, re.IGNORECASE)
            if match:
                original_text = match.group(1).strip()

        clusters = [
            {
                "primary_phrase": "sleepy fox mug",
                "attributes": ["hand-drawn", "cozy colors", "transparent png"],
                "recipient_occasion_terms": ["autumn", "animal lovers"],
                "use_case_terms": ["mug", "tumbler"],
                "competition_level": "differentiable",
                "competition_note": "A popular keyword cluster but few listings offer high quality textured drawing style.",
                "relevance_rank": 95,
            },
            {
                "primary_phrase": "cozy autumn coffee cup clipart",
                "attributes": ["textured style", "transparent background"],
                "recipient_occasion_terms": ["gift for friend", "co-worker"],
                "use_case_terms": ["tote", "sticker"],
                "competition_level": "thin",
                "competition_note": "Low competition for custom texturing styles.",
                "relevance_rank": 80,
            },
            {
                "primary_phrase": "slow morning aesthetics illustration",
                "attributes": ["isolated clipart"],
                "recipient_occasion_terms": ["self gift"],
                "use_case_terms": ["wall art"],
                "competition_level": "saturated",
                "competition_note": "Highly competitive, requires strong differentiation.",
                "relevance_rank": 70,
            },
        ]

        if is_user_or_hybrid:
            concepts = [
                {
                    "title": "Faithful Concept: Sleepy Fox",
                    "description": f"A faithful visualization of the user idea: {original_text}",
                    "differentiation": "Preserves the original concept verbatim while centering the fox curling around a steaming mug in an cozy line art style.",
                    "target_buyer": "People who like quiet autumn mornings and cozy aesthetics",
                    "buyer_use_case": "Morning coffee ritual or seasonal gifting",
                    "seasonality": "seasonal",
                    "risk_level": "low",
                    "risk_note": "No registered trademarks found for cozy sleepy fox designs.",
                    "score": 4.10,
                    "score_breakdown": {
                        "demand": 4,
                        "competition_opportunity": 4,
                        "seasonal_timing": 4,
                        "buyer_clarity": 5,
                        "differentiation": 4,
                        "product_versatility": 4,
                        "ip_safety": 4,
                    },
                    "score_explanation": "Good seasonal demand and clarity.",
                    "fidelity": "High",
                    "origin": "user",
                    "prompt": {
                        "positive_prompt": "A hand-drawn sleepy fox curled around a steaming mug, cosy autumn morning mood, highly detailed pencil texture, isolated on a transparent background.",
                        "negative_prompt": "background, scene, mockup, model, watermark, signature.",
                        "typography_instructions": "Overlay the slogan 'Slow Mornings' below the fox artwork using a warm serif font.",
                        "exact_slogan": "Slow Mornings",
                        "intended_product_uses": ["mug", "tote"],
                        "style_notes": "hand-drawn, textured line work",
                        "palette": "muted autumn tones",
                        "post_generation_checklist": ["transparent background", "uncropped edges"],
                        "generation_metadata": {"aspect": "2:3", "quality_tier": "draft"},
                    },
                },
                {
                    "title": "Optimized Concept: Fox & Forest",
                    "description": "Repositioned version adding forest background elements in a cute illustration style.",
                    "differentiation": "Repositioned to target a broader audience of nature lovers.",
                    "target_buyer": "Nature and animal lovers",
                    "buyer_use_case": "Sublimation designs for tumblers",
                    "seasonality": "evergreen",
                    "risk_level": "low",
                    "risk_note": "None",
                    "score": 3.80,
                    "score_breakdown": {
                        "demand": 3,
                        "competition_opportunity": 4,
                        "seasonal_timing": 4,
                        "buyer_clarity": 4,
                        "differentiation": 4,
                        "product_versatility": 4,
                        "ip_safety": 4,
                    },
                    "score_explanation": "Optimized keyword targeting.",
                    "fidelity": "Medium",
                    "origin": "hybrid",
                    "prompt": {
                        "positive_prompt": "Cute sleepy fox curled in a miniature forest clearing, autumn setting, isolated vector illustration style.",
                        "negative_prompt": "background, scene, mockup, watermark.",
                        "typography_instructions": None,
                        "exact_slogan": None,
                        "intended_product_uses": ["sticker", "mug"],
                        "style_notes": "flat vector style",
                        "palette": "warm forest palette",
                        "post_generation_checklist": ["transparent background"],
                        "generation_metadata": {"aspect": "1:1", "quality_tier": "draft"},
                    },
                },
                {
                    "title": "Experimental Concept: Groovy Coffee Fox",
                    "description": "A retro groovy 70s style fox holding a coffee cup.",
                    "differentiation": "Combines the animal theme with trending groovy aesthetics.",
                    "target_buyer": "Teenagers and young adults",
                    "buyer_use_case": "Laptop stickers or summer tote bags",
                    "seasonality": "evergreen",
                    "risk_level": "medium",
                    "risk_note": "Verify risk for 70s style fonts.",
                    "score": 3.50,
                    "score_breakdown": {
                        "demand": 4,
                        "competition_opportunity": 3,
                        "seasonal_timing": 3,
                        "buyer_clarity": 3,
                        "differentiation": 4,
                        "product_versatility": 4,
                        "ip_safety": 3,
                    },
                    "score_explanation": "Higher trend demand but increased competition.",
                    "fidelity": "Low",
                    "origin": "market",
                    "prompt": {
                        "positive_prompt": "Retro 70s groovy style illustration of a fox holding a coffee mug, vibrant colors, isolated central artwork.",
                        "negative_prompt": "background, mockup, watermark.",
                        "typography_instructions": None,
                        "exact_slogan": None,
                        "intended_product_uses": ["sticker", "tote"],
                        "style_notes": "retro groovy",
                        "palette": "vibrant 70s tones",
                        "post_generation_checklist": ["transparent background"],
                        "generation_metadata": {"aspect": "1:1", "quality_tier": "draft"},
                    },
                },
            ]
        else:
            concepts = [
                {
                    "title": "Autumn Mushroom Clipart",
                    "description": "Detailed hand-drawn watercolor mushrooms for autumn decor.",
                    "differentiation": "Watercolor texture tailored for print-on-demand mugs and pillows.",
                    "target_buyer": "Home decor shoppers",
                    "buyer_use_case": "Cozy autumn aesthetic decoration",
                    "seasonality": "seasonal",
                    "risk_level": "low",
                    "risk_note": "No trademark concerns for generic mushroom clipart.",
                    "score": 4.30,
                    "score_breakdown": {
                        "demand": 5,
                        "competition_opportunity": 4,
                        "seasonal_timing": 4,
                        "buyer_clarity": 4,
                        "differentiation": 4,
                        "product_versatility": 4,
                        "ip_safety": 5,
                    },
                    "score_explanation": "Very high seasonal demand with strong IP safety.",
                    "fidelity": "High",
                    "origin": "market",
                    "prompt": {
                        "positive_prompt": "watercolor style autumn mushrooms, cozy forest floor accents, detailed illustration, isolated on a transparent background.",
                        "negative_prompt": "background, scene, mockup, model, watermark, signature.",
                        "typography_instructions": None,
                        "exact_slogan": None,
                        "intended_product_uses": ["mug", "pillow"],
                        "style_notes": "watercolor illustration",
                        "palette": "earthy brown and orange tones",
                        "post_generation_checklist": ["transparent background"],
                        "generation_metadata": {"aspect": "1:1", "quality_tier": "draft"},
                    },
                },
                {
                    "title": "Minimalist Maple Leaf",
                    "description": "Elegant clean single line art maple leaf illustration.",
                    "differentiation": "Single line minimalist execution for subtle apparel print.",
                    "target_buyer": "Minimalist clothing buyers",
                    "buyer_use_case": "T-shirt sublimation",
                    "seasonality": "seasonal",
                    "risk_level": "low",
                    "risk_note": "No risks.",
                    "score": 3.90,
                    "score_breakdown": {
                        "demand": 4,
                        "competition_opportunity": 3,
                        "seasonal_timing": 4,
                        "buyer_clarity": 4,
                        "differentiation": 4,
                        "product_versatility": 5,
                        "ip_safety": 5,
                    },
                    "score_explanation": "Evergreen potential during fall season.",
                    "fidelity": "High",
                    "origin": "market",
                    "prompt": {
                        "positive_prompt": "minimalist single line art maple leaf, elegant modern style, isolated on transparent background.",
                        "negative_prompt": "background, scene, mockup, watermark.",
                        "typography_instructions": None,
                        "exact_slogan": None,
                        "intended_product_uses": ["tshirt", "tote"],
                        "style_notes": "minimalist line art",
                        "palette": "monochrome black",
                        "post_generation_checklist": ["transparent background"],
                        "generation_metadata": {"aspect": "1:1", "quality_tier": "draft"},
                    },
                },
                {
                    "title": "Retro Groovy Pumpkin",
                    "description": "Vibrant 70s style pumpkin with wavy elements.",
                    "differentiation": "Appeals to halloween retro trend which is highly popular on Etsy.",
                    "target_buyer": "Halloween outfit shoppers",
                    "buyer_use_case": "Apparel printing and stickers",
                    "seasonality": "seasonal",
                    "risk_level": "low",
                    "risk_note": "Safe.",
                    "score": 3.70,
                    "score_breakdown": {
                        "demand": 5,
                        "competition_opportunity": 3,
                        "seasonal_timing": 3,
                        "buyer_clarity": 3,
                        "differentiation": 4,
                        "product_versatility": 4,
                        "ip_safety": 5,
                    },
                    "score_explanation": "High demand, but crowded market segment.",
                    "fidelity": "High",
                    "origin": "market",
                    "prompt": {
                        "positive_prompt": "70s retro groovy pumpkin clipart, warm autumn colors, wavy psychedelic details, isolated vector.",
                        "negative_prompt": "background, mockup, watermark.",
                        "typography_instructions": None,
                        "exact_slogan": None,
                        "intended_product_uses": ["tshirt", "sticker"],
                        "style_notes": "retro groovy",
                        "palette": "orange, cream, brown",
                        "post_generation_checklist": ["transparent background"],
                        "generation_metadata": {"aspect": "1:1", "quality_tier": "draft"},
                    },
                },
            ]

        payload = {
            "confidence": "high",
            "proposed_test": "Create 10 draft listings with the 'watercolor style' concepts to measure click-through rates.",
            "keyword_clusters": clusters,
            "concepts": concepts,
        }

        return TextResponse(
            text=json.dumps(payload),
            input_tokens=len(request.prompt.split()),
            output_tokens=500,
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
