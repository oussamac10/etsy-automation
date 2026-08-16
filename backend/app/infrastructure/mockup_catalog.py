"""Centralized product mapping and placement presets for realistic mockups.

This module provides canonical product aliases, default products, and placement presets
for user-uploaded mockup template workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True)
class MockupProductPreset:
    product_type: str
    display_name: str
    default_left_pct: float = 0.25
    default_top_pct: float = 0.25
    default_width_pct: float = 0.50
    default_height_pct: float = 0.50
    default_blend_mode: str = "multiply"  # "multiply" for fabrics/textured apparel, "over" for opaque hard goods


PRODUCT_PRESETS: dict[str, MockupProductPreset] = {
    "tshirt": MockupProductPreset(
        product_type="tshirt",
        display_name="Unisex Staple T-Shirt",
        default_left_pct=0.28,
        default_top_pct=0.25,
        default_width_pct=0.44,
        default_height_pct=0.48,
        default_blend_mode="multiply",
    ),
    "sweatshirt": MockupProductPreset(
        product_type="sweatshirt",
        display_name="Crewneck Sweatshirt",
        default_left_pct=0.28,
        default_top_pct=0.26,
        default_width_pct=0.44,
        default_height_pct=0.46,
        default_blend_mode="multiply",
    ),
    "tote_bag": MockupProductPreset(
        product_type="tote_bag",
        display_name="Canvas Tote Bag",
        default_left_pct=0.26,
        default_top_pct=0.36,
        default_width_pct=0.48,
        default_height_pct=0.46,
        default_blend_mode="multiply",
    ),
    "mug": MockupProductPreset(
        product_type="mug",
        display_name="Ceramic Mug",
        default_left_pct=0.32,
        default_top_pct=0.32,
        default_width_pct=0.36,
        default_height_pct=0.38,
        default_blend_mode="over",
    ),
    "tumbler": MockupProductPreset(
        product_type="tumbler",
        display_name="Tumbler / Cup",
        default_left_pct=0.30,
        default_top_pct=0.28,
        default_width_pct=0.40,
        default_height_pct=0.48,
        default_blend_mode="over",
    ),
    "poster": MockupProductPreset(
        product_type="poster",
        display_name="Poster / Wall Art",
        default_left_pct=0.20,
        default_top_pct=0.20,
        default_width_pct=0.60,
        default_height_pct=0.60,
        default_blend_mode="over",
    ),
}

DEFAULT_SUPPORTED_PRODUCTS: list[str] = ["tshirt", "sweatshirt", "tote_bag", "mug"]

_PRODUCT_ALIASES: dict[str, str] = {
    "tshirt": "tshirt",
    "t-shirt": "tshirt",
    "t_shirt": "tshirt",
    "tee": "tshirt",
    "shirt": "tshirt",
    "apparel": "tshirt",
    "sweatshirt": "sweatshirt",
    "sweat-shirt": "sweatshirt",
    "sweat_shirt": "sweatshirt",
    "hoodie": "sweatshirt",
    "sweater": "sweatshirt",
    "jumper": "sweatshirt",
    "crewneck": "sweatshirt",
    "tote": "tote_bag",
    "tote_bag": "tote_bag",
    "tote-bag": "tote_bag",
    "tote bag": "tote_bag",
    "bag": "tote_bag",
    "canvas tote": "tote_bag",
    "mug": "mug",
    "cup": "mug",
    "coffee mug": "mug",
    "coffee-mug": "mug",
    "ceramic mug": "mug",
    "tumbler": "tumbler",
    "tumblers": "tumbler",
    "tumbler / cup": "tumbler",
    "tumbler_cup": "tumbler",
    "tumbler-cup": "tumbler",
    "travel mug": "tumbler",
    "poster": "poster",
    "posters": "poster",
    "poster / wall art": "poster",
    "wall art": "poster",
    "art print": "poster",
    "sticker": "sticker",
    "stickers": "sticker",
    "phone case": "phone_case",
    "phone_case": "phone_case",
    "phone cover": "phone_case",
    "candle": "candle",
    "candles": "candle",
    "scented candle": "candle",
}


def normalize_mockup_product(raw: str | None) -> str | None:
    """Normalize user input or alias to canonical product type."""
    if not raw:
        return None
    cleaned = raw.strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    if cleaned in PRODUCT_PRESETS:
        return cleaned
    raw_clean = raw.strip().lower()
    return _PRODUCT_ALIASES.get(raw_clean) or _PRODUCT_ALIASES.get(cleaned)


def get_requested_mockup_products(intended_product_uses: Sequence[str] | None) -> list[str]:
    """Filter intended physical uses down to supported mockup products.

    If none matched or intended_product_uses is empty, returns all standard default products.
    """
    if not intended_product_uses:
        return list(DEFAULT_SUPPORTED_PRODUCTS)

    matched: list[str] = []
    seen: set[str] = set()

    for item in intended_product_uses:
        canonical = normalize_mockup_product(item)
        if canonical and canonical in PRODUCT_PRESETS and canonical not in seen:
            matched.append(canonical)
            seen.add(canonical)

    if not matched:
        return list(DEFAULT_SUPPORTED_PRODUCTS)

    return matched


def get_product_preset(product_type: str) -> MockupProductPreset:
    """Get preset placement for a canonical product type or return a generic preset."""
    canonical = normalize_mockup_product(product_type) or product_type
    return PRODUCT_PRESETS.get(
        canonical,
        MockupProductPreset(
            product_type=canonical,
            display_name=canonical.replace("_", " ").capitalize(),
        ),
    )
