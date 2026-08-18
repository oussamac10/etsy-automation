"""Listing SEO generation service using LLM text providers."""

from __future__ import annotations

import json
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator

from app.domain.tags import (
    MAX_ETSY_TAGS,
    MAX_TAG_LENGTH,
    MAX_TITLE_LENGTH,
    normalize_tag,
    validate_tags,
)
from app.infrastructure.models import DesignPrompt, ProductConcept
from app.ports.errors import ProviderError
from app.ports.providers import TextGenerationProvider, TextRequest


class ListingSeoDraft(BaseModel):
    """Validated structured SEO output from LLM."""

    title: str = Field(..., max_length=MAX_TITLE_LENGTH, description="Etsy listing title <= 140 chars")
    description: str = Field(..., min_length=50, description="Comprehensive digital PNG product description")
    tags: list[str] = Field(..., min_length=MAX_ETSY_TAGS, max_length=MAX_ETSY_TAGS, description="Exactly 13 Etsy tags <= 20 chars each")
    ai_disclosure: str = Field(
        default="This design was created with the assistance of artificial intelligence tools and finalized by a human designer.",
        description="Etsy AI creation disclosure statement",
    )

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        cleaned = re.sub(r"\s+", " ", v.strip())
        if len(cleaned) > MAX_TITLE_LENGTH:
            cleaned = cleaned[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0]
        return cleaned

    @field_validator("tags")
    @classmethod
    def validate_exact_13_tags(cls, v: list[str]) -> list[str]:
        is_valid, accepted, errors = validate_tags(v)
        if not is_valid:
            # Try deduplication and padding
            cleaned_seen: list[str] = []
            for raw_tag in v:
                norm = normalize_tag(raw_tag)
                if norm and len(norm) <= MAX_TAG_LENGTH and norm not in cleaned_seen:
                    cleaned_seen.append(norm)
            if len(cleaned_seen) > MAX_ETSY_TAGS:
                cleaned_seen = cleaned_seen[:MAX_ETSY_TAGS]
            return cleaned_seen
        return accepted


def _build_seo_prompt(
    concept: ProductConcept,
    prompt: DesignPrompt | None,
    keywords: list[str] | None,
) -> str:
    slogan = prompt.exact_slogan if prompt else None
    kw_str = ", ".join(keywords) if keywords else "png digital download, sublimation design, clip art"

    return f"""You are an expert Etsy Print-on-Demand and Digital Download SEO copywriter.
Generate an optimized, high-converting Etsy listing for the following digital PNG artwork:

Product Title/Concept: {concept.title}
Concept Description: {concept.description}
Artwork Slogan: {slogan or 'N/A'}
Target Buyer: {concept.target_buyer or 'Apparel buyers, crafters, gifts'}
Seasonality / Occasion: {concept.seasonality or 'Evergreen'}
Primary Keywords: {kw_str}

CRITICAL ETSY GUIDELINES:
1. TITLE:
   - Max 140 characters.
   - Front-load important buyer-intent keywords (e.g. "PNG Digital Download", "Sublimation Design", theme/slogan).
   - Natural language, no spammy keyword stuffing.
2. DESCRIPTION:
   - Clearly state this is a DIGITAL PNG DOWNLOAD (No physical product will be shipped).
   - High resolution: 4500x5400 px, 300 DPI, transparent background (sRGB).
   - Detail intended uses: Direct-to-Garment (DTG) T-shirts, sweatshirts, mugs, stickers, sublimation, crafts.
   - Instructions on instant download and commercial use rights.
   - Include the Etsy AI disclosure text.
3. TAGS:
   - EXACTLY 13 tags.
   - Each tag must be 20 characters or fewer.
   - No duplicates, no punctuation except spaces or hyphens.
   - Highly relevant search terms (multi-word phrases preferred).
4. AI DISCLOSURE:
   - A concise, professional disclosure statement as required by Etsy for AI-assisted digital products.

Output MUST be a valid JSON object with the following schema:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12", "tag13"],
  "ai_disclosure": "..."
}}
"""


async def generate_listing_seo(
    concept: ProductConcept,
    prompt: DesignPrompt | None,
    keywords: list[str] | None,
    text_provider: TextGenerationProvider,
) -> ListingSeoDraft:
    """Generate and validate Etsy listing copy using the configured text provider."""
    prompt_text = _build_seo_prompt(concept, prompt, keywords)
    request = TextRequest(
        prompt=prompt_text,
        system="You are a professional Etsy SEO generator that outputs strict JSON.",
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

    # Ensure 13 tags even if LLM returned slightly fewer or more
    raw_tags = data.get("tags", [])
    if isinstance(raw_tags, list):
        cleaned_tags: list[str] = []
        for t in raw_tags:
            norm = normalize_tag(str(t))
            if norm and len(norm) <= MAX_TAG_LENGTH and norm not in cleaned_tags:
                cleaned_tags.append(norm)

        # Fallback tags if under 13
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
