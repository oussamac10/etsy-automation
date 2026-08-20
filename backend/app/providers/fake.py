"""Deterministic fake providers.

These are the default in ``local`` and the only implementations available in
Phase 1. They are seeded by their inputs so tests and demos are reproducible,
and none of them performs network I/O or costs money.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import (
    CostEstimate,
    EtsyFileResponse,
    EtsyGateway,
    EtsyImageResponse,
    EtsyListingDraftInput,
    EtsyListingResponse,
    EtsyShop,
    EtsyShopSection,
    EtsyTaxonomyNode,
    EtsyTaxonomyProperty,
    EtsyTokenResponse,
    EtsyUser,
    ImageCandidate,
    ImageRequest,
    ImageResponse,
    SearchQuery,
    SearchResult,
    StoredObject,
    TextRequest,
    TextResponse,
    TrademarkMatch,
    TrademarkSearchPort,
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

        if "seo copywriter" in prompt_lower or "critical etsy guidelines" in prompt_lower:
            concept_title = "Cute Artwork"
            match = re.search(r"Product Title/Concept:\s*([^\n]+)", request.prompt, re.IGNORECASE)
            if match:
                concept_title = match.group(1).strip()

            slogan_match = re.search(r"Artwork Slogan:\s*([^\n]+)", request.prompt, re.IGNORECASE)
            slogan = slogan_match.group(1).strip() if slogan_match and slogan_match.group(1).strip() not in ("N/A", "None", "") else None

            # Clean words from concept title
            words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", concept_title) if len(w) > 2]
            niche_words = [w for w in words if w not in {"the", "and", "for", "with", "concept", "faithful", "market", "hybrid"}]
            main_niche = " ".join(niche_words[:3]) if niche_words else "vintage design"

            generated_title = f"{concept_title[:90]} PNG Digital Download, Sublimation T-Shirt Design"[:140]

            candidate_tags = [
                f"{main_niche[:16]} png"[:20],
                f"{main_niche[:12]} sublimation"[:20],
                f"{main_niche[:13]} clipart"[:20],
                f"{main_niche[:14]} design"[:20],
                f"{main_niche[:14]} tshirt"[:20],
                "png digital download",
                "sublimation design",
                "transparent png",
                "printable art",
                "dtg shirt graphic",
                "instant download",
                "commercial use png",
                "pod graphics file",
                "tshirt graphic",
                "sticker png",
            ]

            seen_tags: set[str] = set()
            unique_tags: list[str] = []
            for t in candidate_tags:
                clean = re.sub(r"[^a-zA-Z0-9\s-]", "", t.strip().lower())
                clean = re.sub(r"\s+", " ", clean)[:20]
                if clean and clean not in seen_tags:
                    seen_tags.add(clean)
                    unique_tags.append(clean)
                if len(unique_tags) == 13:
                    break

            seo_payload = {
                "title": generated_title,
                "description": (
                    f"High-resolution digital PNG download for {concept_title}.\n\n"
                    f"- High Resolution: 4500x5400 px @ 300 DPI, transparent background (sRGB).\n"
                    f"- Intended Uses: DTG T-shirts, sweatshirts, mugs, stickers, sublimation, and crafts.\n"
                    f"- Instant digital download upon purchase. No physical item will be shipped.\n"
                    f"- Commercial use license included for physical end products."
                ),
                "tags": unique_tags[:13],
                "ai_disclosure": "This digital artwork was created with human creative direction and AI design assistance.",
            }

            return TextResponse(
                text=json.dumps(seo_payload),
                input_tokens=len(request.prompt.split()),
                output_tokens=350,
                model="fake-text-seo",
            )

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
                "competition_note": (
                    "A popular keyword cluster but few listings offer high quality textured "
                    "drawing style."
                ),
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
                    "differentiation": (
                        "Preserves the original concept verbatim while centering the fox curling "
                        "around a steaming mug in an cozy line art style."
                    ),
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
                        "positive_prompt": (
                            "A hand-drawn sleepy fox curled around a steaming mug, cosy autumn "
                            "morning mood, highly detailed pencil texture, isolated on a "
                            "transparent background."
                        ),
                        "negative_prompt": (
                            "background, scene, mockup, model, watermark, signature."
                        ),
                        "typography_instructions": (
                            "Overlay the slogan 'Slow Mornings' below the fox artwork using a warm "
                            "serif font."
                        ),
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
                    "description": (
                        "Repositioned version adding forest background elements in a cute "
                        "illustration style."
                    ),
                    "differentiation": (
                        "Repositioned to target a broader audience of nature lovers."
                    ),
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
                        "positive_prompt": (
                            "Cute sleepy fox curled in a miniature forest clearing, autumn "
                            "setting, isolated vector illustration style."
                        ),
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
                        "positive_prompt": (
                            "Retro 70s groovy style illustration of a fox holding a coffee mug, "
                            "vibrant colors, isolated central artwork."
                        ),
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
                    "differentiation": (
                        "Watercolor texture tailored for print-on-demand mugs and pillows."
                    ),
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
                        "positive_prompt": (
                            "watercolor style autumn mushrooms, cozy forest floor accents, "
                            "detailed illustration, isolated on a transparent background."
                        ),
                        "negative_prompt": (
                            "background, scene, mockup, model, watermark, signature."
                        ),
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
                        "positive_prompt": (
                            "minimalist single line art maple leaf, elegant modern style, isolated "
                            "on transparent background."
                        ),
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
                    "differentiation": (
                        "Appeals to halloween retro trend which is highly popular on Etsy."
                    ),
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
                        "positive_prompt": (
                            "70s retro groovy pumpkin clipart, warm autumn colors, wavy "
                            "psychedelic details, isolated vector."
                        ),
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
            "proposed_test": (
                "Create 10 draft listings with the 'watercolor style' concepts to measure "
                "click-through rates."
            ),
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
    """Returns unique mock PNG/SVG bytes and records the idempotency key it saw.

    Simulates multiple candidates, Recraft vs Gemini formats, transient/permanent errors,
    and calculates realistic costs to test budget controls.
    """

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

        # Simulating transient/permanent errors via special prompt strings
        if request.positive_prompt == "trigger-transient-error":
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=FAKE_PROVIDER_NAME,
                operation="image_generation",
                message="Simulated transient network error.",
            )
        elif request.positive_prompt == "trigger-permanent-error":
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=FAKE_PROVIDER_NAME,
                operation="image_generation",
                message="Simulated permanent invalid prompt error.",
            )

        model = request.model or "recraftv4_1"
        is_svg = (request.output_format == "svg") or ("vector" in model)
        mime = "image/svg+xml" if is_svg else "image/png"

        candidates: list[ImageCandidate] = []
        for i in range(request.candidate_count):
            if is_svg:
                # Deterministic SVG bytes that differ by index (unique checksums)
                svg_str = (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                    '<rect width="10" height="10" fill="blue"/>'
                    f'<text y="5">{request.idempotency_key}-{i}</text>'
                    "</svg>"
                )
                content = svg_str.encode()
            else:
                # PNG bytes with a small suffix to differentiate checksums
                content = _TRANSPARENT_PNG + f"-candidate-{i}".encode()

            candidates.append(
                ImageCandidate(
                    image_bytes=content,
                    mime_type=mime,
                    width=request.width or 1024,
                    height=request.height or 1024,
                )
            )

        # Determine cost based on model/provider rules
        if "pro" in model:
            unit_price = Decimal("0.21") if "recraft" in model else Decimal("0.15")
        elif "vector" in model:
            unit_price = Decimal("0.08")
        else:
            unit_price = Decimal("0.035") if "recraft" in model else Decimal("0.03")

        cost_usd = unit_price * request.candidate_count

        return ImageResponse(
            candidates=candidates,
            model=model,
            provider_request_id=_seed(request.idempotency_key)[:16],
            cost_usd=cost_usd,
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

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)


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


class FakeTrademarkSearchAdapter(TrademarkSearchPort):
    """Deterministic in-memory trademark search adapter for tests and local development."""

    def __init__(self, canned_matches: dict[str, list[TrademarkMatch]] | None = None) -> None:
        self._canned = canned_matches or {}

    def set_canned_matches(self, phrase: str, matches: list[TrademarkMatch]) -> None:
        self._canned[phrase.lower().strip()] = matches

    async def search_trademark(self, phrase: str) -> list[TrademarkMatch]:
        norm = phrase.lower().strip()
        if norm in self._canned:
            return self._canned[norm]

        # Built-in deterministic mock triggers
        if any(brand in norm for brand in ("disney", "marvel", "starbucks", "nike", "barbie")):
            return [
                TrademarkMatch(
                    mark_text=phrase.upper(),
                    serial_number="88123456",
                    registration_number="5678901",
                    status="REGISTERED AND RENEWED",
                    is_live=True,
                    goods_services="Downloadable graphics; clothing, namely t-shirts, sweatshirts.",
                    classes=["009", "025"],
                    owner="Brand Holdings LLC",
                    filing_date="2020-01-01",
                    registration_date="2021-01-01",
                    source_url="https://tsdr.uspto.gov/#caseNumber=88123456",
                )
            ]

        if "warning" in norm or "partial" in norm:
            return [
                TrademarkMatch(
                    mark_text=f"{phrase.upper()} CAFE",
                    serial_number="88654321",
                    registration_number="5432109",
                    status="REGISTERED",
                    is_live=True,
                    goods_services="Coffee, tea, and restaurant services.",
                    classes=["030", "043"],
                    owner="Warning Ventures Inc.",
                    filing_date="2019-05-10",
                    registration_date="2020-08-15",
                    source_url="https://tsdr.uspto.gov/#caseNumber=88654321",
                )
            ]

        if "dead" in norm:
            return [
                TrademarkMatch(
                    mark_text=phrase.upper(),
                    serial_number="77111222",
                    registration_number=None,
                    status="CANCELLED - SECTION 8",
                    is_live=False,
                    goods_services="Apparel and shirts.",
                    classes=["025"],
                    owner="Old Corp LLC",
                    filing_date="2010-01-01",
                )
            ]

        # Default clean
        return []


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


class FakeEtsyProvider(EtsyGateway):
    """Deterministic in-memory Etsy provider for tests and local development.

    Simulates OAuth token exchange, token refresh, shop resolution, draft listing creation,
    image uploads, and digital ZIP uploads without network I/O.
    """

    def __init__(
        self,
        *,
        default_shop_id: str = "12345678",
        default_shop_name: str = "CraftyDesignStudio",
        default_user_id: str = "98765432",
    ) -> None:
        self.default_shop_id = default_shop_id
        self.default_shop_name = default_shop_name
        self.default_user_id = default_user_id

        # Call tracking & recorded payloads
        self.exchanged_codes: list[dict[str, str]] = []
        self.refreshed_tokens: list[str] = []
        self.created_listings: list[dict[str, Any]] = []
        self.uploaded_images: list[dict[str, Any]] = []
        self.uploaded_files: list[dict[str, Any]] = []
        self.updated_properties: list[dict[str, Any]] = []
        self.updated_inventory: list[dict[str, Any]] = []

        # Fake shop sections
        self.fake_shop_sections: list[EtsyShopSection] = [
            EtsyShopSection(shop_section_id="101", title="Christmas PNGs", rank=1, active_listing_count=5),
            EtsyShopSection(shop_section_id="102", title="Fall PNGs", rank=2, active_listing_count=3),
            EtsyShopSection(shop_section_id="103", title="Book Lover PNGs", rank=3, active_listing_count=2),
        ]

        # Error triggers for tests
        self.fail_exchange: bool = False
        self.fail_refresh: bool = False
        self.fail_create_listing: bool = False
        self.fail_upload_image: bool = False
        self.fail_upload_file: bool = False
        self.fail_get_sections: bool = False
        self.get_listing_rate_limited: bool = False
        self.get_listing_server_error: bool = False
        self.get_listing_timeout: bool = False
        self.deleted_listing_ids: set[str] = set()
        self.rate_limit_after_calls: int | None = None
        self.call_count: int = 0
        self.revoked_token: bool = False

    def mark_listing_deleted(self, listing_id: str) -> None:
        self.deleted_listing_ids.add(listing_id)

    async def exchange_code_for_token(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> EtsyTokenResponse:
        self.call_count += 1
        if self.fail_exchange:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="etsy",
                operation="exchange_code",
                message="Invalid or expired authorization code.",
            )
        self.exchanged_codes.append(
            {"code": code, "code_verifier": code_verifier, "redirect_uri": redirect_uri}
        )
        return EtsyTokenResponse(
            access_token=f"{self.default_user_id}.fake_access_token_123",
            refresh_token=f"{self.default_user_id}.fake_refresh_token_456",
            expires_in=3600,
            token_type="Bearer",
            scope=["listings_r", "listings_w", "shops_r"],
        )

    async def refresh_token(self, *, refresh_token: str) -> EtsyTokenResponse:
        self.call_count += 1
        if self.fail_refresh or self.revoked_token:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="etsy",
                operation="refresh_token",
                message="Refresh token has been revoked or expired.",
            )
        self.refreshed_tokens.append(refresh_token)
        return EtsyTokenResponse(
            access_token=f"{self.default_user_id}.refreshed_access_token_{len(self.refreshed_tokens)}",
            refresh_token=f"{self.default_user_id}.refreshed_refresh_token_{len(self.refreshed_tokens)}",
            expires_in=3600,
            token_type="Bearer",
            scope=["listings_r", "listings_w", "shops_r"],
        )

    async def get_me(self, *, access_token: str) -> EtsyUser:
        self.call_count += 1
        if self.revoked_token:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="etsy",
                operation="get_me",
                message="OAuth token revoked.",
            )
        return EtsyUser(
            user_id=self.default_user_id,
            primary_email="owner@etsycraftstudio.com",
            first_name="Studio Owner",
        )

    async def get_user_shops(self, *, access_token: str, user_id: str) -> list[EtsyShop]:
        self.call_count += 1
        if self.revoked_token:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="etsy",
                operation="get_user_shops",
                message="OAuth token revoked.",
            )
        return [
            EtsyShop(
                shop_id=self.default_shop_id,
                shop_name=self.default_shop_name,
                user_id=user_id,
                url=f"https://www.etsy.com/shop/{self.default_shop_name}",
            )
        ]

    async def create_draft_listing(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing: EtsyListingDraftInput,
        idempotency_key: str | None = None,
    ) -> EtsyListingResponse:
        self.call_count += 1
        if self.rate_limit_after_calls and self.call_count > self.rate_limit_after_calls:
            raise ProviderError(
                kind=ProviderErrorKind.RATE_LIMITED,
                provider="etsy",
                operation="create_draft_listing",
                message="Etsy API rate limit exceeded (429).",
                retry_after_seconds=2.0,
            )
        if self.fail_create_listing:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="etsy",
                operation="create_draft_listing",
                message="Simulated temporary Etsy server error (503).",
            )
        if self.revoked_token:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="etsy",
                operation="create_draft_listing",
                message="Token expired or revoked.",
            )

        # Deterministic listing ID
        seed = _seed(shop_id, listing.title, idempotency_key or "")
        listing_id = str(int(seed[:10], 16))

        record = {
            "listing_id": listing_id,
            "shop_id": shop_id,
            "title": listing.title,
            "description": listing.description,
            "tags": list(listing.tags),
            "price_cents": listing.price_cents,
            "currency": listing.currency,
            "taxonomy_id": listing.taxonomy_id,
            "quantity": listing.quantity,
            "sku": listing.sku,
            "shop_section_id": listing.shop_section_id,
            "should_auto_renew": listing.should_auto_renew,
            "state": "draft",  # Hardcoded draft guarantee
            "idempotency_key": idempotency_key,
        }
        self.created_listings.append(record)

        return EtsyListingResponse(
            listing_id=listing_id,
            shop_id=shop_id,
            title=listing.title,
            state="draft",
            url=f"https://www.etsy.com/listing/{listing_id}",
        )

    async def upload_listing_image(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing_id: str,
        image_bytes: bytes,
        filename: str = "mockup.jpg",
        rank: int = 1,
        alt_text: str | None = None,
    ) -> EtsyImageResponse:
        self.call_count += 1
        if self.fail_upload_image:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="etsy",
                operation="upload_listing_image",
                message="Simulated image upload timeout / network error.",
            )

        seed = _seed(listing_id, filename, str(rank))
        image_id = str(int(seed[:9], 16))

        self.uploaded_images.append(
            {
                "listing_image_id": image_id,
                "listing_id": listing_id,
                "shop_id": shop_id,
                "filename": filename,
                "rank": rank,
                "bytes_len": len(image_bytes),
                "alt_text": alt_text,
            }
        )

        return EtsyImageResponse(
            listing_image_id=image_id,
            listing_id=listing_id,
            rank=rank,
            url=f"https://i.etsystatic.com/fake/{image_id}.jpg",
        )

    async def upload_listing_file(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing_id: str,
        file_bytes: bytes,
        filename: str = "package.zip",
        rank: int = 1,
    ) -> EtsyFileResponse:
        self.call_count += 1
        if self.fail_upload_file:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="etsy",
                operation="upload_listing_file",
                message="Simulated digital file upload timeout.",
            )

        seed = _seed(listing_id, filename, str(len(file_bytes)))
        file_id = str(int(seed[:8], 16))

        self.uploaded_files.append(
            {
                "listing_file_id": file_id,
                "listing_id": listing_id,
                "shop_id": shop_id,
                "filename": filename,
                "rank": rank,
                "filesize": len(file_bytes),
            }
        )

        return EtsyFileResponse(
            listing_file_id=file_id,
            listing_id=listing_id,
            rank=rank,
            filename=filename,
            filesize=len(file_bytes),
        )

    async def get_listing(
        self, *, access_token: str, shop_id: str, listing_id: str
    ) -> EtsyListingResponse | None:
        self.call_count += 1
        if self.revoked_token:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="etsy",
                operation="get_listing",
                message="OAuth token revoked.",
            )
        if self.get_listing_rate_limited:
            raise ProviderError(
                kind=ProviderErrorKind.RATE_LIMITED,
                provider="etsy",
                operation="get_listing",
                message="Etsy API rate limit reached (429).",
                retry_after_seconds=5.0,
            )
        if self.get_listing_server_error:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="etsy",
                operation="get_listing",
                message="Etsy remote server error (503).",
            )
        if self.get_listing_timeout:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="etsy",
                operation="get_listing",
                message="Etsy request timed out.",
            )
        if listing_id in self.deleted_listing_ids:
            return None
        for item in self.created_listings:
            if item["listing_id"] == listing_id:
                return EtsyListingResponse(
                    listing_id=listing_id,
                    shop_id=shop_id,
                    title=item["title"],
                    state="draft",
                    url=f"https://www.etsy.com/listing/{listing_id}",
                )
        return EtsyListingResponse(
            listing_id=listing_id,
            shop_id=shop_id,
            title="Etsy Draft Listing",
            state="draft",
            url=f"https://www.etsy.com/listing/{listing_id}",
        )

    async def get_seller_taxonomy_nodes(self) -> list[EtsyTaxonomyNode]:
        self.call_count += 1
        return [
            EtsyTaxonomyNode(
                id=66,
                level=0,
                name="Art & Collectibles",
                full_path="Art & Collectibles",
                children=(
                    EtsyTaxonomyNode(
                        id=70,
                        level=1,
                        name="Drawing & Illustration",
                        parent_id=66,
                        full_path="Art & Collectibles > Drawing & Illustration",
                        children=(
                            EtsyTaxonomyNode(
                                id=77,
                                level=2,
                                name="Digital",
                                parent_id=70,
                                full_path="Art & Collectibles > Drawing & Illustration > Digital",
                            ),
                        ),
                    ),
                    EtsyTaxonomyNode(
                        id=2077,
                        level=1,
                        name="Prints",
                        parent_id=66,
                        full_path="Art & Collectibles > Prints",
                        children=(
                            EtsyTaxonomyNode(
                                id=2078,
                                level=2,
                                name="Digital Prints",
                                parent_id=2077,
                                full_path="Art & Collectibles > Prints > Digital Prints",
                            ),
                        ),
                    ),
                ),
            ),
            EtsyTaxonomyNode(
                id=562,
                level=0,
                name="Craft Supplies & Tools",
                full_path="Craft Supplies & Tools",
                children=(
                    EtsyTaxonomyNode(
                        id=563,
                        level=1,
                        name="Canvas & Surfaces",
                        parent_id=562,
                        full_path="Craft Supplies & Tools > Canvas & Surfaces",
                        children=(
                            EtsyTaxonomyNode(
                                id=564,
                                level=2,
                                name="Stencils, Templates & Transfers",
                                parent_id=563,
                                full_path="Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers",
                                children=(
                                    EtsyTaxonomyNode(
                                        id=6844,
                                        level=3,
                                        name="Clip Art & Image Files",
                                        parent_id=564,
                                        full_path="Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files",
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            EtsyTaxonomyNode(
                id=891,
                level=0,
                name="Home & Living",
                full_path="Home & Living",
                children=(
                    EtsyTaxonomyNode(
                        id=892,
                        level=1,
                        name="Kitchen & Dining",
                        parent_id=891,
                        full_path="Home & Living > Kitchen & Dining",
                        children=(
                            EtsyTaxonomyNode(
                                id=1049,
                                level=2,
                                name="Plates",
                                parent_id=892,
                                full_path="Home & Living > Kitchen & Dining > Plates",
                            ),
                        ),
                    ),
                ),
            ),
        ]

    async def get_shop_sections(self, *, access_token: str, shop_id: str) -> list[EtsyShopSection]:
        self.call_count += 1
        if self.fail_get_sections:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="etsy",
                operation="get_shop_sections",
                message="Failed to fetch shop sections.",
            )
        return list(self.fake_shop_sections)

    async def create_shop_section(self, *, access_token: str, shop_id: str, title: str) -> EtsyShopSection:
        self.call_count += 1
        sec_id = str(len(self.fake_shop_sections) + 101)
        sec = EtsyShopSection(
            shop_section_id=sec_id,
            title=title.strip(),
            rank=len(self.fake_shop_sections) + 1,
            active_listing_count=0,
        )
        self.fake_shop_sections.append(sec)
        return sec

    async def get_taxonomy_properties(self, *, taxonomy_id: int) -> list[EtsyTaxonomyProperty]:
        self.call_count += 1
        from app.domain.taxonomy_properties import FAKE_TEST_TAXONOMY_PROPERTIES

        props: list[EtsyTaxonomyProperty] = []
        for raw in FAKE_TEST_TAXONOMY_PROPERTIES:
            props.append(
                EtsyTaxonomyProperty(
                    property_id=int(raw["property_id"]),
                    name=str(raw["name"]),
                    is_required=bool(raw.get("is_required", False)),
                    supports_attributes=bool(raw.get("supports_attributes", False)),
                    is_multivalued=bool(raw.get("is_multivalued", False)),
                    possible_values=list(raw.get("possible_values", [])),
                )
            )
        return props

    async def update_listing_property(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing_id: str,
        property_id: int,
        value_ids: list[int] | None = None,
        values: list[str] | None = None,
    ) -> bool:
        self.call_count += 1
        self.updated_properties.append(
            {
                "shop_id": shop_id,
                "listing_id": listing_id,
                "property_id": property_id,
                "value_ids": list(value_ids or []),
                "values": list(values or []),
            }
        )
        return True

    async def update_listing_inventory(
        self,
        *,
        access_token: str,
        listing_id: str,
        sku: str,
        price_cents: int,
        quantity: int,
    ) -> bool:
        self.call_count += 1
        self.updated_inventory.append(
            {
                "listing_id": listing_id,
                "sku": sku,
                "price_cents": price_cents,
                "quantity": quantity,
            }
        )
        return True

