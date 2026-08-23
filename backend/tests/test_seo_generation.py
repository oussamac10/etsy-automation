"""Unit and regression tests for high-quality Etsy listing SEO copy generation."""

from __future__ import annotations

import uuid

import pytest

from app.application.seo import (
    ListingSeoDraft,
    _build_seo_prompt,
    generate_listing_seo,
)
from app.domain.seo_quality import (
    detect_duplicate_phrases,
    validate_description_quality,
    validate_summary_quality,
    validate_title_quality,
)
from app.infrastructure.models import DesignPrompt, ProductConcept
from app.providers.fake import FakeTextProvider


@pytest.fixture
def sample_concept() -> ProductConcept:
    return ProductConcept(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        title="Kawaii Medical Equipment Lineup",
        description="Five cute kawaii medical device characters in soft pastel colors including MRI, CT scanner, and syringe.",
        target_buyer="Radiology technologists, pediatric nurses, healthcare workers",
        seasonality="Evergreen",
    )


@pytest.fixture
def sample_prompt() -> DesignPrompt:
    return DesignPrompt(
        id=uuid.uuid4(),
        concept_id=uuid.uuid4(),
        version=1,
        positive_prompt="Kawaii medical equipment clipart with cute smiling faces",
        negative_prompt="photorealistic, blurry, watermark",
        exact_slogan=None,
    )


class TestSeoQualityValidators:
    def test_title_quality_valid(self) -> None:
        title = "Kawaii Medical Equipment PNG, Radiology Tech Sublimation Design, MRI CT Scanner Clipart, Pediatric Nurse Digital Download"
        is_valid, issues = validate_title_quality(title)
        assert is_valid, f"Expected title to be valid but got issues: {issues}"
        assert len(issues) == 0

    def test_title_quality_flags_excessive_png(self) -> None:
        title = "Kawaii Medical Equipment PNG, Cute Radiology PNG Sublimation, Scanner PNG Clipart"
        is_valid, issues = validate_title_quality(title)
        assert not is_valid
        assert any('"PNG" appears' in iss for iss in issues)

    def test_title_quality_flags_too_many_sequential_caps(self) -> None:
        title = "Kawaii Medical Equipment PNG, MRI CT PET EKG Scanner Clipart"
        is_valid, issues = validate_title_quality(title)
        assert not is_valid
        assert any("sequential capital letters" in iss for iss in issues)

    def test_description_quality_valid(self) -> None:
        desc = (
            "DIGITAL DOWNLOAD – PNG FILE ONLY\n\n"
            "This kawaii medical equipment design features cute anthropomorphic medical devices in soft pastel colors.\n\n"
            "WHAT YOU WILL RECEIVE\n"
            "• High-resolution transparent background PNG (4500 × 5400 px @ 300 DPI, sRGB)\n"
            "• Dark-shirt optimized transparent PNG\n\n"
            "PERFECT FOR\n"
            "• Direct-to-Garment (DTG) printing\n"
            "• T-shirts, scrubs jackets, and sweatshirts\n"
            "• Sublimation apparel and tote bags\n"
            "• Mugs, tumblers, and water bottles\n"
            "• Stickers, decals, and badge reels\n\n"
            "INSTANT DOWNLOAD\n"
            "Your digital files are made available by Etsy immediately after payment confirmation. Access them anytime under your Etsy account Purchases section.\n\n"
            "COMMERCIAL USE\n"
            "Commercial use allowed on physical finished products (such as apparel, mugs, stickers, and gifts). You may not resell or share the digital file.\n\n"
            "AI DISCLOSURE\n"
            "This artwork was created with the assistance of AI generation tools and then professionally edited, refined, and prepared for digital production.\n\n"
            "PRINT NOTE\n"
            "Colors may vary slightly depending on screen, printer, ink, material, and print settings."
        )
        metadata = {
            "width": 4500,
            "height": 5400,
            "dpi": 300,
            "variants": ["Dark-shirt optimized"],
        }
        is_valid, issues = validate_description_quality(desc, metadata)
        assert is_valid, f"Expected description to be valid but got issues: {issues}"

    def test_description_quality_flags_ai_promotional_fluff(self) -> None:
        desc = (
            "DIGITAL DOWNLOAD – PNG FILE ONLY\n\n"
            "Bring smiles to the pediatric ward and unleash your creativity with this must-have addition!\n\n"
            "WHAT YOU WILL RECEIVE\n"
            "• High-resolution PNG (4500 x 5400 px @ 300 DPI)\n\n"
            "PERFECT FOR\n• Crafts\n\n"
            "INSTANT DOWNLOAD\nFiles available instantly.\n\n"
            "COMMERCIAL USE\nCommercial use permitted.\n\n"
            "AI DISCLOSURE\nCreated with AI.\n\n"
            "PRINT NOTE\nColors may vary."
        )
        is_valid, issues = validate_description_quality(desc)
        assert not is_valid
        assert any("promotional AI fluff" in iss for iss in issues)

    def test_summary_quality_valid(self) -> None:
        summary = "Cute kawaii medical equipment PNG with MRI and CT scanner characters in pastel colors. High-res 4500x5400 px transparent file for shirts, scrubs, stickers and sublimation."
        is_valid, issues = validate_summary_quality(
            summary=summary,
            title="Kawaii Medical Equipment PNG, Radiology Tech Sublimation",
            description="DIGITAL DOWNLOAD – PNG FILE ONLY\n\nFull description here...",
        )
        assert is_valid, f"Expected summary to be valid but got issues: {issues}"
        assert len(summary) <= 200

    def test_summary_quality_flags_over_200_chars(self) -> None:
        long_summary = "A" * 205
        is_valid, issues = validate_summary_quality(long_summary)
        assert not is_valid
        assert any("exceeds 200 characters" in iss for iss in issues)

    def test_summary_quality_flags_legal_boilerplate(self) -> None:
        summary = "Cute medical equipment PNG with commercial license included. Terms of use: personal and physical products only."
        is_valid, issues = validate_summary_quality(summary)
        assert not is_valid
        assert any("legal terms" in iss for iss in issues)

    def test_detect_duplicate_phrases(self) -> None:
        text = "Cute kawaii medical PNG clipart with cute PNG digital download and cute kawaii characters PNG"
        duplicates = detect_duplicate_phrases(text, max_allowed=2)
        assert len(duplicates) >= 1
        assert any("png" in d.lower() or "cute" in d.lower() for d in duplicates)


class TestSeoGenerationService:
    @pytest.mark.asyncio
    async def test_generate_listing_seo_with_fake_provider(
        self,
        sample_concept: ProductConcept,
        sample_prompt: DesignPrompt,
    ) -> None:
        provider = FakeTextProvider()
        keywords = ["kawaii medical png", "radiology tech sublimation", "ct scanner clipart"]
        production_meta = {
            "width": 4500,
            "height": 5400,
            "dpi": 300,
            "has_transparent_background": True,
            "variants": ["Dark Shirt PNG"],
        }

        seo_draft = await generate_listing_seo(
            concept=sample_concept,
            prompt=sample_prompt,
            keywords=keywords,
            text_provider=provider,
            artwork_summary="Five cute kawaii medical device characters in soft pastel colors",
            production_meta=production_meta,
            target_field="all",
        )

        assert isinstance(seo_draft, ListingSeoDraft)
        assert len(seo_draft.title) <= 140
        assert len(seo_draft.shopping_cart_summary) <= 200
        assert len(seo_draft.tags) == 13
        assert "DIGITAL DOWNLOAD" in seo_draft.description
        assert "WHAT YOU WILL RECEIVE" in seo_draft.description
        assert "PERFECT FOR" in seo_draft.description
        assert "COMMERCIAL USE" in seo_draft.description
        assert "AI DISCLOSURE" in seo_draft.description

    def test_build_seo_prompt_includes_metadata_and_instructions(
        self,
        sample_concept: ProductConcept,
        sample_prompt: DesignPrompt,
    ) -> None:
        production_meta = {
            "width": 4500,
            "height": 5400,
            "dpi": 300,
            "has_transparent_background": True,
            "variants": ["Dark Shirt PNG", "Light Shirt PNG"],
        }
        prompt_text = _build_seo_prompt(
            concept=sample_concept,
            prompt=sample_prompt,
            keywords=["medical png", "radiology sublimation"],
            artwork_summary="Kawaii medical machines",
            production_meta=production_meta,
            license_rules="Physical product commercial use only.",
            target_field="title",
        )

        assert "4500 × 5400" in prompt_text
        assert "300 DPI" in prompt_text
        assert "Dark Shirt PNG" in prompt_text
        assert "Light Shirt PNG" in prompt_text
        assert "Physical product commercial use only." in prompt_text
        assert "FOCUS INSTRUCTION" in prompt_text
        assert 'Do NOT repeat "PNG" more than once' in prompt_text
        assert "Max 200 chars" in prompt_text


class TestPricingDomain:
    def test_format_currency_amount(self) -> None:
        from app.domain.pricing import format_currency_amount

        assert format_currency_amount(499, "USD") == "$4.99"
        assert format_currency_amount(550, "EUR") == "€5.50"
        assert format_currency_amount(450, "GBP") == "£4.50"
        assert format_currency_amount(499, "CAD") == "CA$4.99"

    def test_valid_price_minor_units(self) -> None:
        from app.domain.pricing import validate_price_minor_units

        valid, err = validate_price_minor_units(499, "USD")
        assert valid is True
        assert err is None

    def test_invalid_price_zero_or_none(self) -> None:
        from app.domain.pricing import validate_price_minor_units

        valid, err = validate_price_minor_units(0, "USD")
        assert valid is False
        assert "greater than zero" in (err or "")

        valid, err = validate_price_minor_units(None, "USD")
        assert valid is False
        assert "is required" in (err or "")

    def test_invalid_price_below_etsy_minimum(self) -> None:
        from app.domain.pricing import validate_price_minor_units

        valid, err = validate_price_minor_units(10, "USD")
        assert valid is False
        assert "lower than Etsy minimum" in (err or "")

    def test_invalid_price_above_etsy_maximum(self) -> None:
        from app.domain.pricing import validate_price_minor_units

        valid, err = validate_price_minor_units(6000000, "USD")
        assert valid is False
        assert "exceeds safety limit" in (err or "")


class TestPricingRecommendationEngine:
    def test_recommendation_with_bundle_design(self) -> None:
        from app.domain.pricing import calculate_price_recommendation

        rec = calculate_price_recommendation(
            title="Vintage Christmas Sublimation Bundle PNG Clipart",
            tags=["retro sublimation bundle", "christmas png pack", "vintage clipart"],
            currency="USD",
        )
        assert rec.recommended_minor_units >= 499
        assert rec.currency == "USD"
        assert "$4.99" in rec.formatted_price or "$6.99" in rec.formatted_price
        assert len(rec.factors) > 0

    def test_recommendation_eur_shop(self) -> None:
        from app.domain.pricing import calculate_price_recommendation

        rec = calculate_price_recommendation(
            title="Cute Fall Baking PNG Design",
            tags=["fall baking png", "cute aesthetic pumpkin"],
            currency="EUR",
        )
        assert rec.currency == "EUR"
        assert "€" in rec.formatted_price
        assert rec.recommended_minor_units in (399, 449, 499, 549)


class TestSkuGenerator:
    def test_derive_shop_prefix(self) -> None:
        from app.domain.sku_generator import derive_shop_prefix

        assert derive_shop_prefix("NovaCraftPixel") == "NOVA"
        assert derive_shop_prefix("Digital Art Studio") == "DAS"
        assert derive_shop_prefix("Vintage") == "VINT"
        assert derive_shop_prefix("") == "ET"
        assert derive_shop_prefix(None) == "ET"

    def test_extract_sku_keywords(self) -> None:
        from app.domain.sku_generator import extract_sku_keywords

        assert extract_sku_keywords("Retro Christmas Baking PNG Sublimation") in (
            "RETRO-CHRIS",
            "RETRO-BAKIN",
        )
        assert extract_sku_keywords("Pumpkin Spice Clipart") in ("PUMPK-SPICE", "PUMPK")

    def test_generate_sku_stability(self) -> None:
        from app.domain.sku_generator import generate_sku

        workflow_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
        sku1 = generate_sku(
            shop_name="NovaCraftPixel",
            title_or_concept="Retro Christmas Baking PNG Sublimation Clipart",
            workflow_id=workflow_id,
        )
        sku2 = generate_sku(
            shop_name="NovaCraftPixel",
            title_or_concept="Retro Christmas Baking PNG Sublimation Clipart",
            workflow_id=workflow_id,
        )
        assert sku1 == sku2
        assert sku1.startswith("NOVA-")
        assert len(sku1) <= 32

    def test_generate_sku_different_workflow_ids_differ(self) -> None:
        from app.domain.sku_generator import generate_sku

        wf1 = uuid.UUID("11111111-2222-3333-4444-555555555555")
        wf2 = uuid.UUID("99999999-8888-7777-6666-555555555555")
        sku1 = generate_sku("Shop A", "Art Title", wf1)
        sku2 = generate_sku("Shop A", "Art Title", wf2)
        assert sku1 != sku2
