"""Listing SEO generation service using LLM text providers."""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

from app.domain.seo_quality import (
    MAX_CART_SUMMARY_LENGTH,
    validate_description_quality,
    validate_summary_quality,
    validate_title_quality,
)
from app.domain.tags import (
    MAX_ETSY_TAGS,
    MAX_TAG_LENGTH,
    MAX_TITLE_LENGTH,
    normalize_tag,
    sanitize_etsy_title,
    validate_tags,
)
from app.infrastructure.models import DesignPrompt, ProductConcept
from app.ports.errors import ProviderError
from app.ports.providers import TextGenerationProvider, TextRequest

SeoTargetField = Literal["all", "title", "description", "shopping_cart_summary", "tags"]


class ListingSeoDraft(BaseModel):
    """Validated structured SEO output from LLM."""

    title: str = Field(..., description="Etsy listing title <= 140 chars")
    description: str = Field(..., description="Structured digital PNG product description")
    shopping_cart_summary: str = Field(
        default="",
        description="Concise 1-2 sentence shopping cart summary <= 200 chars",
    )
    tags: list[str] = Field(default_factory=list, description="Etsy tags (automatically formatted to exactly 13)")
    ai_disclosure: str = Field(
        default="This artwork was created with the assistance of AI generation tools and then professionally edited, refined, and prepared for digital production.",
        description="Etsy AI creation disclosure statement",
    )

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        return sanitize_etsy_title(str(v))

    @field_validator("shopping_cart_summary")
    @classmethod
    def clean_summary(cls, v: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(v or "").strip())
        if len(cleaned) > MAX_CART_SUMMARY_LENGTH:
            cleaned = cleaned[:MAX_CART_SUMMARY_LENGTH].rsplit(" ", 1)[0]
        return cleaned

    @field_validator("tags")
    @classmethod
    def validate_exact_13_tags(cls, v: list[str]) -> list[str]:
        cleaned_seen: list[str] = []
        for raw_tag in v:
            norm = normalize_tag(str(raw_tag))
            if norm and len(norm) <= MAX_TAG_LENGTH and norm not in cleaned_seen:
                cleaned_seen.append(norm)

        fallbacks = [
            "png digital download",
            "sublimation design",
            "dtg shirt graphic",
            "transparent png",
            "printable art",
            "clipart graphic",
            "instant download",
            "tshirt design png",
            "commercial use png",
            "pod graphics",
            "mug design download",
            "sticker png",
            "digital craft file",
        ]
        for fb in fallbacks:
            if len(cleaned_seen) >= MAX_ETSY_TAGS:
                break
            if fb not in cleaned_seen:
                cleaned_seen.append(fb)

        return cleaned_seen[:MAX_ETSY_TAGS]


def _build_seo_prompt(
    concept: ProductConcept,
    prompt: DesignPrompt | None,
    keywords: list[str] | None,
    artwork_summary: str | None = None,
    production_meta: dict[str, Any] | None = None,
    license_rules: str | None = None,
    target_field: SeoTargetField = "all",
) -> str:
    slogan = prompt.exact_slogan if prompt else None
    kw_str = ", ".join(keywords) if keywords else "png digital download, sublimation design, clipart"

    # Resolve metadata details
    meta = production_meta or {}
    width = meta.get("width", 4500)
    height = meta.get("height", 5400)
    dpi = meta.get("dpi", 300)
    is_transparent = meta.get("has_transparent_background", True)
    variants = meta.get("variants") or []

    # File deliverables list for description
    deliverables_lines = [
        f"• High-resolution transparent background PNG ({width} × {height} px @ {dpi} DPI, sRGB)"
    ]
    if variants:
        for v in variants:
            deliverables_lines.append(f"• {v} transparent PNG deliverable")

    deliverables_block = "\n".join(deliverables_lines)

    license_block = license_rules or (
        "Commercial use allowed on physical finished products (such as apparel, t-shirts, sweatshirts, "
        "tote bags, mugs, stickers, and gifts). You may not resell, redistribute, or share the digital file."
    )

    target_instruction = ""
    if target_field != "all":
        target_instruction = f"\nFOCUS INSTRUCTION: The user requested to regenerate specifically '{target_field}'. Ensure exceptional quality for '{target_field}' while providing consistent full output.\n"

    return f"""You are an experienced, professional Etsy seller and digital product copywriter.
Generate natural, high-converting, buyer-friendly Etsy listing copy for this digital PNG artwork.
Write directly and clearly for real human buyers. Do NOT write like a marketing chatbot and do NOT keyword-stuff.
{target_instruction}
PRODUCT CONTEXT:
- Concept / Title: {concept.title}
- Concept Details: {concept.description}
- Artwork Summary: {artwork_summary or (prompt.positive_prompt if prompt else 'N/A')}
- Slogan / Text in Art: {slogan or 'None'}
- Target Buyer / Niche: {concept.target_buyer or 'Apparel crafters, sublimation creators, POD buyers'}
- Seasonality / Occasion: {concept.seasonality or 'Evergreen'}
- Primary Keywords: {kw_str}

ACTUAL PRODUCT SPECIFICATIONS (DO NOT INVENT DIFFERENT DIMENSIONS OR FILE COUNTS):
- Dimensions: {width} × {height} pixels
- Resolution: {dpi} DPI
- Background: {'Transparent PNG' if is_transparent else 'Opaque PNG'}
- Included Variants: {', '.join(variants) if variants else 'Master PNG only'}
- Commercial License Terms: {license_block}

CRITICAL COPY GUIDELINES:

1. ETSY TITLE (Max 140 chars):
   - Preferred formula: [Primary product/niche keyword], [secondary use/search phrase], [specific subject/role], [digital format/use]
   - Put the strongest buyer-intent keyword first.
   - Use natural professional terms (e.g. "Radiology Tech", "Pediatric Nurse") instead of awkward abbreviations.
   - Do NOT repeat "PNG" more than once.
   - Do NOT repeat "digital download" or synonyms multiple times.
   - Avoid filler words and do not stuff synonyms just to fill the 140 character count.
   - Keep at most 3 words starting with sequential capital letters (e.g. PNG, SVG, MRI, CT).

2. ETSY DESCRIPTION (Structured & Scan-Friendly):
   Use the exact following section headers:

   DIGITAL DOWNLOAD – PNG FILE ONLY

   [1–2 sentences natural introduction describing the artwork accurately without hype. Maximum 1–2 adjectives per sentence. No promotional fluff like 'Bring smiles to...' or 'Elevate your...']

   WHAT YOU WILL RECEIVE
{deliverables_block}

   PERFECT FOR
   • Direct-to-Garment (DTG) printing
   • T-shirts, sweatshirts, and hoodies
   • Sublimation apparel and tote bags
   • Mugs, tumblers, and glassware
   • Stickers, decals, and digital planners

   INSTANT DOWNLOAD
   Your digital files are made available by Etsy immediately after payment confirmation. Access them anytime under your Etsy account Purchases section.

   COMMERCIAL USE
   {license_block}

   AI DISCLOSURE
   This artwork was created with the assistance of AI generation tools and then professionally edited, refined, and prepared for digital production.

   PRINT NOTE
   Colors may vary slightly depending on screen, printer, ink, material, and print settings.

3. SHOPPING CART SUMMARY (Max 200 chars):
   - 1–2 concise, factual, buyer-oriented sentences.
   - Formula: [What it is] + [visual style] + [size/format] + [main use]
   - Example: "Cute kawaii medical equipment PNG with MRI and scanner characters in pastel colors. High-res {width}x{height} px transparent file for shirts, scrubs, stickers and sublimation."
   - Do NOT include legal/license text, AI disclosure, shipping text, or keyword stuffing.

4. ETSY TAGS:
   - Exactly 13 tags, each 20 characters or fewer.
   - Multi-word search terms.

Output MUST be a valid JSON object with the following schema:
{{
  "title": "...",
  "description": "...",
  "shopping_cart_summary": "...",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12", "tag13"],
  "ai_disclosure": "This artwork was created with the assistance of AI generation tools and then professionally edited, refined, and prepared for digital production."
}}
"""


async def generate_listing_seo(
    concept: ProductConcept,
    prompt: DesignPrompt | None,
    keywords: list[str] | None,
    text_provider: TextGenerationProvider,
    artwork_summary: str | None = None,
    production_meta: dict[str, Any] | None = None,
    license_rules: str | None = None,
    target_field: SeoTargetField = "all",
) -> ListingSeoDraft:
    """Generate and validate Etsy listing copy using the configured text provider."""
    prompt_text = _build_seo_prompt(
        concept=concept,
        prompt=prompt,
        keywords=keywords,
        artwork_summary=artwork_summary,
        production_meta=production_meta,
        license_rules=license_rules,
        target_field=target_field,
    )
    request = TextRequest(
        prompt=prompt_text,
        system="You are a professional Etsy SEO copywriter that outputs strict JSON.",
        max_output_tokens=2048,
        schema_class=ListingSeoDraft,
    )

    response = await text_provider.generate(request)
    raw_text = response.text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text)

    try:
        data: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        from app.ports.errors import ProviderErrorKind

        raise ProviderError(
            kind=ProviderErrorKind.PERMANENT,
            provider="text_generation",
            operation="generate_seo",
            message=f"Failed to parse JSON from SEO text generation: {exc}",
        ) from exc

    # Clean title
    if "title" in data:
        data["title"] = sanitize_etsy_title(str(data["title"]))

    # Clean shopping cart summary
    if "shopping_cart_summary" in data:
        summary_clean = re.sub(r"\s+", " ", str(data["shopping_cart_summary"]).strip())
        if len(summary_clean) > MAX_CART_SUMMARY_LENGTH:
            summary_clean = summary_clean[:MAX_CART_SUMMARY_LENGTH].rsplit(" ", 1)[0]
        data["shopping_cart_summary"] = summary_clean

    # Ensure 13 tags
    raw_tags = data.get("tags", [])
    if isinstance(raw_tags, list):
        cleaned_tags: list[str] = []
        for t in raw_tags:
            norm = normalize_tag(str(t))
            if norm and len(norm) <= MAX_TAG_LENGTH and norm not in cleaned_tags:
                cleaned_tags.append(norm)

        fallbacks = [
            "png digital download",
            "sublimation design",
            "dtg shirt graphic",
            "transparent png",
            "printable art",
            "clipart graphic",
            "instant download",
            "tshirt design png",
            "commercial use png",
            "pod graphics",
            "mug design download",
            "sticker png",
            "digital craft file",
        ]
        for fb in fallbacks:
            if len(cleaned_tags) >= MAX_ETSY_TAGS:
                break
            if fb not in cleaned_tags:
                cleaned_tags.append(fb)

        data["tags"] = cleaned_tags[:MAX_ETSY_TAGS]

    return ListingSeoDraft.model_validate(data)
