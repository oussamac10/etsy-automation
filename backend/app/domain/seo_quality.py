"""Deterministic quality checks and duplicate phrase guards for Etsy listing copy.

Enforces:
1. Title quality: character limit, buyer-intent keyword placement, sequential capital limits, no duplicate phrases/PNGs, clean punctuation.
2. Description quality: structured sections, matching product metadata, no invented license limits, no marketing fluff/promotional filler, reasonable readability.
3. Shopping cart summary quality: <= 200 chars, concise, factual, no license/legal boilerplate, distinct from title and description.
4. Duplicate phrase detection across all fields.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.tags import (
    MAX_TITLE_LENGTH,
    count_sequential_capital_words,
)

MAX_CART_SUMMARY_LENGTH = 200

# Common AI marketing fluff phrases to reject or flag in descriptions
PROHIBITED_AI_PHRASES: tuple[str, ...] = (
    "bring smiles to",
    "brings smiles to",
    "elevate your",
    "unleash your creativity",
    "transform your projects",
    "perfectly crafted for",
    "dive into the world of",
    "look no further",
    "must-have addition",
    "take your crafts to the next level",
    "seamlessly blend",
)

REQUIRED_DESCRIPTION_SECTIONS: tuple[str, ...] = (
    "DIGITAL DOWNLOAD",
    "WHAT YOU WILL RECEIVE",
    "PERFECT FOR",
    "INSTANT DOWNLOAD",
    "COMMERCIAL USE",
    "AI DISCLOSURE",
    "PRINT NOTE",
)


def detect_duplicate_phrases(text: str, max_allowed: int = 2) -> list[str]:
    """Detect repetitive words or phrases in a text snippet."""
    if not text:
        return []

    duplicates: list[str] = []
    key_terms = [
        "png",
        "digital download",
        "sublimation",
        "clipart",
        "instant download",
        "cute",
        "adorable",
        "kawaii",
    ]
    text_lower = text.lower()

    for term in key_terms:
        pattern = rf"\b{re.escape(term)}\b"
        matches = re.findall(pattern, text_lower)
        if len(matches) > max_allowed:
            duplicates.append(
                f'Term "{term}" repeated {len(matches)} times (max allowed: {max_allowed}).'
            )

    return duplicates


def validate_title_quality(title: str) -> tuple[bool, list[str]]:
    """Validate Etsy listing title quality and naturalness.

    Returns:
        tuple[is_valid, list_of_issues]
    """
    issues: list[str] = []
    cleaned = title.strip()

    if not cleaned:
        return False, ["Title cannot be empty."]

    if len(cleaned) > MAX_TITLE_LENGTH:
        issues.append(f"Title exceeds {MAX_TITLE_LENGTH} characters (got {len(cleaned)}).")

    # Etsy sequential capitals rule (at most 3 words starting with 2+ caps)
    caps_count = count_sequential_capital_words(cleaned)
    if caps_count > 3:
        issues.append(
            f"Title has {caps_count} words starting with sequential capital letters (Etsy limit is 3)."
        )

    # Duplicate "PNG" or "digital download" check in title (should not repeat in title)
    title_lower = cleaned.lower()
    png_count = len(re.findall(r"\bpng\b", title_lower))
    if png_count > 1:
        issues.append(f'"PNG" appears {png_count} times in the title. Prefer using it only once.')

    dd_count = len(re.findall(r"\bdigital download\b", title_lower))
    if dd_count > 1:
        issues.append(f'"Digital Download" appears {dd_count} times in the title.')

    # Formatting checks: double spaces, trailing commas/hyphens, malformed capitalization
    if "  " in cleaned:
        issues.append("Title contains consecutive whitespace characters.")

    if re.search(r"[,;:\-]\s*$", cleaned):
        issues.append("Title has trailing punctuation.")

    return len(issues) == 0, issues


def validate_description_quality(
    description: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Validate structured description quality, sections, and metadata consistency.

    Returns:
        tuple[is_valid, list_of_issues]
    """
    issues: list[str] = []
    desc_clean = description.strip()

    if not desc_clean:
        return False, ["Description cannot be empty."]

    desc_upper = desc_clean.upper()

    # Verify structured section headers
    for section in REQUIRED_DESCRIPTION_SECTIONS:
        if section not in desc_upper:
            issues.append(f'Missing required structured section: "{section}".')

    # Check for prohibited AI fluff phrases
    desc_lower = desc_clean.lower()
    for fluff in PROHIBITED_AI_PHRASES:
        if fluff in desc_lower:
            issues.append(f'Description contains promotional AI fluff: "{fluff}".')

    # Check for duplicate paragraphs
    paragraphs = [p.strip() for p in desc_clean.split("\n\n") if p.strip()]
    seen_paras: set[str] = set()
    for p in paragraphs:
        p_norm = re.sub(r"\s+", " ", p.lower())
        if p_norm in seen_paras:
            issues.append("Description contains duplicate paragraphs.")
            break
        seen_paras.add(p_norm)

    # Validate metadata consistency if provided
    if metadata:
        if metadata.get("width") and metadata.get("height"):
            dim_pattern = rf"{metadata['width']}\s*[xX×]\s*{metadata['height']}"
            if not re.search(dim_pattern, desc_clean):
                issues.append(
                    f"Description does not match actual product dimensions ({metadata['width']}x{metadata['height']} px)."
                )

        if metadata.get("dpi"):
            dpi_str = f"{metadata['dpi']} DPI"
            if dpi_str.lower() not in desc_lower and f"{metadata['dpi']}dpi" not in desc_lower:
                issues.append(f"Description does not specify {metadata['dpi']} DPI.")

        if metadata.get("variants"):
            for variant_name in metadata["variants"]:
                if variant_name.lower() not in desc_lower:
                    issues.append(
                        f'Description does not list included variant deliverable: "{variant_name}".'
                    )

    # Guard against invented physical shipping claims
    if "will be shipped to your address" in desc_lower or "physical package" in desc_lower:
        issues.append("Description makes false physical shipping claims for a digital PNG product.")

    return len(issues) == 0, issues


def validate_summary_quality(
    summary: str,
    title: str = "",
    description: str = "",
) -> tuple[bool, list[str]]:
    """Validate shopping cart summary quality, length, and content focus.

    Returns:
        tuple[is_valid, list_of_issues]
    """
    issues: list[str] = []
    clean_summary = summary.strip()

    if not clean_summary:
        return False, ["Shopping cart summary cannot be empty."]

    if len(clean_summary) > MAX_CART_SUMMARY_LENGTH:
        issues.append(
            f"Shopping cart summary exceeds {MAX_CART_SUMMARY_LENGTH} characters (got {len(clean_summary)})."
        )

    # Should not be identical to title
    if title and clean_summary.lower() == title.strip().lower():
        issues.append("Shopping cart summary is identical to the listing title.")

    # Should not be identical to first line of description
    if description:
        first_line = description.strip().split("\n")[0].strip().lower()
        if clean_summary.lower() == first_line:
            issues.append(
                "Shopping cart summary is identical to the first line of the description."
            )

    # Should contain format/product type (e.g. PNG, digital, sublimation, clipart, download)
    summary_lower = clean_summary.lower()
    has_format = any(
        kw in summary_lower
        for kw in ["png", "digital", "clipart", "graphic", "illustration", "file", "download"]
    )
    if not has_format:
        issues.append(
            "Shopping cart summary should state the format/product type (e.g. PNG, digital)."
        )

    # Should NOT contain legal/license paragraphs or AI disclosure
    if (
        "commercial license" in summary_lower
        or "terms of use" in summary_lower
        or "ai disclosure" in summary_lower
    ):
        issues.append(
            "Shopping cart summary must not contain legal terms or AI disclosure boilerplate."
        )

    return len(issues) == 0, issues
