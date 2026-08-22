"""Listing SEO generation service using LLM text providers."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Literal
from pydantic import BaseModel, Field, field_validator
import structlog

from app.domain.errors import DomainError
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
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import TextGenerationProvider, TextRequest

if TYPE_CHECKING:
    from app.application.listing_context import ListingGenerationContext

logger = structlog.get_logger(__name__)

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
        sanitized = sanitize_etsy_title(str(v or ""))
        if len(sanitized) > MAX_TITLE_LENGTH:
            truncated = sanitized[:MAX_TITLE_LENGTH]
            if "," in truncated:
                sanitized = truncated.rsplit(",", 1)[0].strip()
            else:
                sanitized = truncated.rsplit(" ", 1)[0].strip()
        return sanitized

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


def validate_semantic_consistency(
    seo_draft: ListingSeoDraft,
    concept_title: str,
    concept_description: str = "",
    forbidden_anchors: list[str] | None = None,
) -> None:
    """Validate that generated SEO copy matches the active concept and does not contain forbidden/stale anchors."""
    combined_text = f"{seo_draft.title} {seo_draft.shopping_cart_summary} {seo_draft.description}".lower()
    clean_concept_title = concept_title.strip().lower()

    # Extract meaningful anchor tokens from active concept title
    concept_tokens = [
        w for w in re.findall(r"[a-z0-9]+", clean_concept_title)
        if len(w) > 2 and w not in {
            "the", "and", "for", "with", "png", "svg", "eps", "clipart",
            "design", "graphic", "download", "sublimation"
        }
    ]

    # Verify at least one primary concept token exists in generated copy
    combined_tokens = set(re.findall(r"[a-z0-9]+", combined_text))
    if concept_tokens and not any(
        token in combined_tokens or any(token in ct for ct in combined_tokens)
        for token in concept_tokens
    ):
        logger.warning(
            "seo_semantic_anchor_missing",
            concept_title=concept_title,
            generated_title=seo_draft.title,
            concept_tokens=concept_tokens,
        )
        raise DomainError(
            f"Generated listing copy failed semantic consistency check: "
            f"None of the active concept anchors ({', '.join(concept_tokens[:4])}) were found in the output."
        )

    # Verify forbidden anchors are absent using strict whole-token matching
    if forbidden_anchors:
        concept_words_set = set(re.findall(r"[a-z0-9]+", clean_concept_title))
        for fa in forbidden_anchors:
            fa_clean = fa.strip().lower()
            if not fa_clean or len(fa_clean) < 4:
                continue
            # Skip if fa_clean matches or overlaps any active concept token
            if fa_clean in concept_words_set or any(fa_clean in cw or cw in fa_clean for cw in concept_words_set):
                continue
            # Check whole-word presence in combined tokens
            if fa_clean in combined_tokens:
                logger.warning(
                    "seo_forbidden_anchor_detected",
                    forbidden_anchor=fa_clean,
                    concept_title=concept_title,
                    generated_title=seo_draft.title,
                )
                raise DomainError(
                    f"Generated listing copy contains stale/forbidden anchor '{fa_clean}' from an unselected concept."
                )


def _build_seo_prompt(
    concept: ProductConcept | Any,
    prompt: DesignPrompt | None = None,
    keywords: list[str] | None = None,
    artwork_summary: str | None = None,
    production_meta: dict[str, Any] | None = None,
    license_rules: str | None = None,
    target_field: SeoTargetField = "all",
) -> str:
    # Check if a ListingGenerationContext was passed directly as concept
    if hasattr(concept, "concept") and hasattr(concept, "artwork"):
        ctx = concept
        concept_title = ctx.concept.title
        concept_desc = ctx.concept.description
        target_buyer = ctx.concept.target_buyer or "Apparel crafters, sublimation creators, POD buyers"
        niche = ctx.concept.niche
        seasonality = ctx.concept.seasonality or "Evergreen"
        slogan = ctx.concept.slogan
        kw_list = ctx.concept.keywords
        art_sum = ctx.artwork.visual_summary or artwork_summary
        width = ctx.production.width
        height = ctx.production.height
        dpi = ctx.production.dpi
        is_transparent = ctx.production.has_transparent_background
        variants = ctx.production.variants
        license_block = ctx.buyer_package.license_terms
    else:
        concept_title = getattr(concept, "title", "Digital Artwork")
        concept_desc = getattr(concept, "description", "")
        target_buyer = getattr(concept, "target_buyer", None) or "Apparel crafters, sublimation creators, POD buyers"
        niche = getattr(concept, "niche", "Digital PNG Crafters & Sublimation")
        seasonality = getattr(concept, "seasonality", None) or "Evergreen"
        slogan = prompt.exact_slogan if prompt else None
        kw_list = keywords or []
        art_sum = artwork_summary or (prompt.positive_prompt if prompt else concept_desc)
        meta = production_meta or {}
        width = meta.get("width", 4500)
        height = meta.get("height", 5400)
        dpi = meta.get("dpi", 300)
        is_transparent = meta.get("has_transparent_background", True)
        variants = meta.get("variants") or []
        license_block = license_rules or (
            "Commercial use allowed on physical finished products (such as apparel, t-shirts, sweatshirts, "
            "tote bags, mugs, stickers, and gifts). You may not resell, redistribute, or share the digital file."
        )

    kw_str = ", ".join(kw_list) if kw_list else "png digital download, sublimation design, clipart"

    # File deliverables list for description
    deliverables_lines = [
        f"• High-resolution transparent background PNG ({width} × {height} px @ {dpi} DPI, sRGB)"
    ]
    if variants:
        for v in variants:
            deliverables_lines.append(f"• {v} transparent PNG deliverable")

    deliverables_block = "\n".join(deliverables_lines)

    target_instruction = ""
    if target_field != "all":
        target_instruction = f"\nFOCUS INSTRUCTION: The user requested to regenerate specifically '{target_field}'. Ensure exceptional quality for '{target_field}' while providing consistent full output.\n"

    return f"""You are an experienced, professional Etsy seller and digital product copywriter.
Generate natural, high-converting, buyer-friendly Etsy listing copy for this digital PNG artwork.
Write directly and clearly for real human buyers. Do NOT write like a marketing chatbot and do NOT keyword-stuff.
{target_instruction}
ACTIVE PRODUCT CONTEXT (ONLY GENERATE FOR THIS PRODUCT):
- Concept / Title: {concept_title}
- Concept Details: {concept_desc}
- Artwork Summary: {art_sum or 'N/A'}
- Slogan / Text in Art: {slogan or 'None'}
- Target Buyer: {target_buyer}
- Niche / Theme: {niche}
- Seasonality / Occasion: {seasonality}
- Primary High-Intent Keywords: {kw_str}

ACTUAL PRODUCT SPECIFICATIONS (DO NOT INVENT DIFFERENT DIMENSIONS OR FILE COUNTS):
- Dimensions: {width} × {height} pixels
- Resolution: {dpi} DPI
- Background: {'Transparent PNG' if is_transparent else 'Opaque PNG'}
- Included Variants: {', '.join(variants) if variants else 'Master PNG only'}
- Commercial License Terms: {license_block}

CRITICAL DIRECTIVE:
Generate listing content ONLY for the product described above ("{concept_title}").
Do not reuse details from previous products, campaigns, conversations, or cached examples.
If the current artwork/context does not contain skeletons, coffee, dark academia, or other unrelated themes, do not mention them.

CRITICAL COPY GUIDELINES:

1. ETSY TITLE (Max 140 chars):
   - Preferred formula: [Primary product/niche keyword], [secondary use/search phrase], [specific subject/role], [digital format/use]
   - Put the strongest buyer-intent keyword first.
   - Use natural professional terms instead of awkward abbreviations.
   - Do NOT repeat "PNG" more than once.
   - Do NOT repeat "digital download" or synonyms multiple times.
   - Avoid filler words and do not stuff synonyms just to fill the 140 character count.
   - Keep at most 3 words starting with sequential capital letters (e.g. PNG, SVG).

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
    concept: ProductConcept | Any,
    prompt: DesignPrompt | None = None,
    keywords: list[str] | None = None,
    text_provider: TextGenerationProvider | None = None,
    artwork_summary: str | None = None,
    production_meta: dict[str, Any] | None = None,
    license_rules: str | None = None,
    target_field: SeoTargetField = "all",
    forbidden_anchors: list[str] | None = None,
    context: ListingGenerationContext | None = None,
) -> ListingSeoDraft:
    """Generate and validate Etsy listing copy using the configured text provider."""
    # Allow passing context directly
    if context is not None:
        concept_obj = context
        concept_title = context.concept.title
        concept_desc = context.concept.description
    elif hasattr(concept, "concept") and hasattr(concept, "artwork"):
        concept_obj = concept
        concept_title = concept.concept.title
        concept_desc = concept.concept.description
    else:
        concept_obj = concept
        concept_title = getattr(concept, "title", "Digital Artwork")
        concept_desc = getattr(concept, "description", "")

    if text_provider is None:
        from app.providers.fake import FakeTextProvider
        text_provider = FakeTextProvider()

    prompt_text = _build_seo_prompt(
        concept=concept_obj,
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
        max_output_tokens=4096,
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
        raise ProviderError(
            kind=ProviderErrorKind.PERMANENT,
            provider="text_generation",
            operation="generate_seo",
            message=f"Failed to parse JSON from SEO text generation: {exc}",
        ) from exc

    # Clean title
    raw_title = sanitize_etsy_title(str(data.get("title") or concept_title))
    if len(raw_title) > MAX_TITLE_LENGTH:
        truncated = raw_title[:MAX_TITLE_LENGTH]
        if "," in truncated:
            raw_title = truncated.rsplit(",", 1)[0].strip()
        else:
            raw_title = truncated.rsplit(" ", 1)[0].strip()
    data["title"] = raw_title

    # Clean shopping cart summary
    raw_summary = re.sub(r"\s+", " ", str(data.get("shopping_cart_summary") or "").strip())
    if not raw_summary:
        raw_summary = f"{concept_title} PNG digital download. High-resolution transparent design for shirts, mugs, stickers and crafts."
    if len(raw_summary) > MAX_CART_SUMMARY_LENGTH:
        raw_summary = raw_summary[:MAX_CART_SUMMARY_LENGTH].rsplit(" ", 1)[0].strip()
    data["shopping_cart_summary"] = raw_summary

    # Ensure description is present
    if not data.get("description"):
        data["description"] = (
            f"DIGITAL DOWNLOAD – PNG FILE ONLY\n\n"
            f"{concept_desc or concept_title}\n\n"
            f"WHAT YOU WILL RECEIVE\n"
            f"• High-resolution transparent background PNG (4500 × 5400 px @ 300 DPI)\n\n"
            f"PERFECT FOR\n"
            f"• Direct-to-Garment (DTG) printing\n"
            f"• T-shirts, sweatshirts, and hoodies\n"
            f"• Sublimation apparel and tote bags\n"
            f"• Mugs, tumblers, and glassware\n"
            f"• Stickers, decals, and badge reels\n\n"
            f"INSTANT DOWNLOAD\n"
            f"Your digital files are made available by Etsy immediately after payment confirmation.\n\n"
            f"COMMERCIAL USE\n"
            f"Commercial use allowed on physical finished products. Digital resale or redistribution is prohibited.\n\n"
            f"AI DISCLOSURE\n"
            f"This artwork was created with the assistance of AI generation tools and then professionally edited, refined, and prepared for digital production.\n\n"
            f"PRINT NOTE\n"
            f"Colors may vary slightly depending on screen, printer, ink, material, and print settings."
        )

    # Ensure AI disclosure is present
    if not data.get("ai_disclosure"):
        data["ai_disclosure"] = "This artwork was created with the assistance of AI generation tools and then professionally edited, refined, and prepared for digital production."

    # Ensure exactly 13 tags
    raw_tags = data.get("tags", [])
    cleaned_tags: list[str] = []
    if isinstance(raw_tags, list):
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

    while len(cleaned_tags) < MAX_ETSY_TAGS:
        cleaned_tags.append(f"craft design {len(cleaned_tags) + 1}")

    data["tags"] = cleaned_tags[:MAX_ETSY_TAGS]

    draft = ListingSeoDraft.model_validate(data)

    # Semantic consistency check
    validate_semantic_consistency(
        seo_draft=draft,
        concept_title=concept_title,
        concept_description=concept_desc,
        forbidden_anchors=forbidden_anchors,
    )

    logger.info(
        "listing_seo_generated",
        concept_title=concept_title,
        title=draft.title,
        tags_count=len(draft.tags),
        target_field=target_field,
    )

    return draft
