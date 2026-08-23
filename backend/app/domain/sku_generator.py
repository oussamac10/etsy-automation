"""Deterministic internal SKU generator for Etsy digital listings."""

from __future__ import annotations

import re
import uuid

# Stopwords to omit from SKU keyword extraction
SKU_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "with",
        "in",
        "on",
        "at",
        "by",
        "png",
        "digital",
        "download",
        "design",
        "clipart",
        "sublimation",
        "instant",
        "file",
        "files",
        "art",
        "graphic",
        "graphics",
        "print",
        "dtg",
    }
)


def derive_shop_prefix(shop_name: str | None) -> str:
    """Extract a 2-4 letter uppercase prefix from shop name."""
    if not shop_name or not shop_name.strip():
        return "ET"

    # Clean words
    words = re.findall(r"[A-Za-z0-9]+", shop_name)
    if not words:
        return "ET"

    if len(words) >= 3:
        prefix = "".join(w[0] for w in words[:3]).upper()
    elif len(words) == 2:
        prefix = (words[0][:2] + words[1][:2]).upper()
    else:
        prefix = words[0][:4].upper()

    return prefix if prefix else "ET"


def extract_sku_keywords(title: str, max_words: int = 2) -> str:
    """Extract 1-2 distinctive slugified keywords from title."""
    words = re.findall(r"[A-Za-z0-9]+", title)
    meaningful = [w.upper() for w in words if w.lower() not in SKU_STOPWORDS and len(w) >= 3]

    if not meaningful:
        meaningful = [w.upper() for w in words if len(w) >= 2][:max_words]

    selected = meaningful[:max_words]
    if not selected:
        return "ART"

    # Truncate each word to 5 chars max for readability
    return "-".join(w[:5] for w in selected)


def generate_sku(
    shop_name: str | None,
    title_or_concept: str,
    workflow_id: uuid.UUID | str,
) -> str:
    """Generate a clean, deterministic, human-readable SKU.

    Format: {SHOP_PREFIX}-{KEYWORDS}-{SHORT_HASH}
    Example: NC-XMAS-BAKE-4A8F
    """
    prefix = derive_shop_prefix(shop_name)
    keywords = extract_sku_keywords(title_or_concept)

    # Deterministic short hash from workflow UUID
    wf_str = str(workflow_id).replace("-", "")
    short_hash = wf_str[:4].upper() if len(wf_str) >= 4 else "0001"

    sku = f"{prefix}-{keywords}-{short_hash}"
    # Enforce safe character set and max length
    sku_cleaned = re.sub(r"[^A-Z0-9\-]", "", sku)[:32]
    return sku_cleaned
