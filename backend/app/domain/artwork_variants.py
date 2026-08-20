"""Domain definitions, enums, prompt builders, and validation for artwork color variants.

Enables creating alternate color-safe versions of an approved master PNG
(e.g., dark-shirt friendly, light-shirt friendly, black accent, white accent, custom color)
without mutating the original master artwork.
"""

from __future__ import annotations

from enum import StrEnum
import hashlib
import re
from typing import Any, Final

DEFAULT_PROMPT_VERSION: Final[str] = "color-variant-v1"


class VariantType(StrEnum):
    """Supported color variant types for digital PNG products."""

    DARK_SHIRT = "dark_shirt"
    LIGHT_SHIRT = "light_shirt"
    BLACK_ACCENT = "black_accent"
    WHITE_ACCENT = "white_accent"
    CUSTOM = "custom"


class VariantStatus(StrEnum):
    """Lifecycle status of a generated color variant."""

    GENERATING = "generating"
    READY = "ready"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


VARIANT_TYPE_LABELS: Final[dict[VariantType, str]] = {
    VariantType.DARK_SHIRT: "Dark Shirt Version",
    VariantType.LIGHT_SHIRT: "Light Shirt Version",
    VariantType.BLACK_ACCENT: "Black Accent Version",
    VariantType.WHITE_ACCENT: "White / Cream Accent Version",
    VariantType.CUSTOM: "Custom Color Version",
}

VARIANT_TYPE_DESCRIPTIONS: Final[dict[VariantType, str]] = {
    VariantType.DARK_SHIRT: "Light/cream high-contrast outlines and elements optimized for black & dark fabric",
    VariantType.LIGHT_SHIRT: "Dark/charcoal high-contrast outlines and elements optimized for white & light fabric",
    VariantType.BLACK_ACCENT: "Deep rich black accent lines and typography with clean contrast",
    VariantType.WHITE_ACCENT: "Crisp white/cream accent lines and typography with clean contrast",
    VariantType.CUSTOM: "Recolors designated elements to your chosen brand HEX palette",
}


def sanitize_hex_color(hex_str: str | None) -> str:
    """Validate and normalize a 3- or 6-digit hex color code."""
    if not hex_str:
        return "#FFFFFF"
    cleaned = hex_str.strip()
    if not cleaned.startswith("#"):
        cleaned = f"#{cleaned}"
    if re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", cleaned):
        return cleaned.upper()
    return "#FFFFFF"


def build_variant_prompt(
    variant_type: VariantType,
    *,
    custom_color: str | None = None,
    original_positive_prompt: str | None = None,
    custom_instructions: str | None = None,
) -> tuple[str, str, str]:
    """Build deterministic positive and negative prompts and return (positive, negative, prompt_version).

    All variant prompts strictly mandate:
    1. Perfect transparent background (alpha channel only).
    2. Preservation of core shapes, composition, text layout, and details.
    3. Target color replacement for contrast safety on garments.
    """
    version = DEFAULT_PROMPT_VERSION
    sanitized_color = sanitize_hex_color(custom_color)

    base_context = (
        f"Original artwork reference context: {original_positive_prompt.strip()}"
        if original_positive_prompt
        else "Reference digital graphic design"
    )

    if variant_type == VariantType.DARK_SHIRT:
        positive = (
            f"Modify the reference graphic design for optimal visibility on dark-colored apparel and black t-shirts. "
            f"{base_context}. "
            f"Preserve the exact composition, silhouette, subject details, texture, and character styling from the reference image. "
            f"Convert all black, near-black, and dark colored outlines, text, and internal details into clean, high-contrast warm cream (#F5E6C8) and bright off-white (#FFFFFF) tones. "
            f"Ensure all elements pop vividly against a dark background while preserving the original non-dark color accents. "
            f"Completely isolated graphic on a clean transparent background, zero backdrop."
        )
        negative = (
            "black background, dark background, fabric mockup, t-shirt template, model, dark outlines, invisible text, "
            "drop shadow, border frame, blurry edges, clipping, low resolution."
        )

    elif variant_type == VariantType.LIGHT_SHIRT:
        positive = (
            f"Modify the reference graphic design for optimal visibility on light-colored apparel and white t-shirts. "
            f"{base_context}. "
            f"Preserve the exact composition, silhouette, subject details, texture, and character styling from the reference image. "
            f"Convert all white, near-white, and pale light colored outlines, text, and internal details into clean, high-contrast dark charcoal (#1A1A1A) and deep rich tones. "
            f"Ensure all elements pop vividly against a pure white background while preserving the original non-light color accents. "
            f"Completely isolated graphic on a clean transparent background, zero backdrop."
        )
        negative = (
            "white background, paper background, fabric mockup, t-shirt template, model, washed out lines, pale outlines, "
            "drop shadow, border frame, blurry edges, clipping, low resolution."
        )

    elif variant_type == VariantType.BLACK_ACCENT:
        positive = (
            f"Recolor the reference graphic design to a bold black accent version. "
            f"{base_context}. "
            f"Preserve the exact composition, subject matter, linework, and silhouette from the reference image. "
            f"Transform key highlights, secondary accents, and primary strokes into deep saturated black and rich charcoal tones. "
            f"Crisp sharp edges, vector-like clarity, completely isolated on a clean transparent background."
        )
        negative = (
            "background scene, fabric mockup, t-shirt template, model, blurry edges, faded lines, clipping, low resolution."
        )

    elif variant_type == VariantType.WHITE_ACCENT:
        positive = (
            f"Recolor the reference graphic design to a crisp white/cream accent version. "
            f"{base_context}. "
            f"Preserve the exact composition, subject matter, linework, and silhouette from the reference image. "
            f"Transform key highlights, secondary accents, and primary strokes into crisp white (#FFFFFF) and delicate cream tones. "
            f"Crisp sharp edges, vector-like clarity, completely isolated on a clean transparent background."
        )
        negative = (
            "background scene, fabric mockup, t-shirt template, model, blurry edges, faded lines, clipping, low resolution."
        )

    elif variant_type == VariantType.CUSTOM:
        positive = (
            f"Recolor the reference graphic design with custom accent color {sanitized_color}. "
            f"{base_context}. "
            f"Preserve the exact composition, subject matter, linework, and silhouette from the reference image. "
            f"Replace primary accent elements, highlighted features, and secondary decorative colors with the exact target color {sanitized_color} while keeping harmonious contrast. "
            f"Crisp sharp edges, vector-like clarity, completely isolated on a clean transparent background."
        )
        negative = (
            "background scene, fabric mockup, t-shirt template, model, blurry edges, muddy colors, clipping, low resolution."
        )

    else:
        positive = f"Refine color balance of reference graphic: {base_context} on transparent background."
        negative = "background, scene, mockup, watermark."

    if custom_instructions and custom_instructions.strip():
        positive = f"{positive} Special user directive: {custom_instructions.strip()}."

    return positive, negative, version


def is_valid_artwork_variant_asset(asset_provenance: dict[str, Any] | None) -> bool:
    """Check if an asset's provenance indicates it is a valid artwork color variant."""
    if not asset_provenance or not isinstance(asset_provenance, dict):
        return False
    return asset_provenance.get("kind") == "artwork_variant"


def filter_workflow_artwork_variants(assets: list[Any]) -> list[Any]:
    """Filter and sort artwork variants for a workflow."""
    variants = [a for a in assets if is_valid_artwork_variant_asset(a.provenance)]
    # Sort approved first, then ready, then by created_at desc
    status_order = {
        VariantStatus.APPROVED.value: 0,
        VariantStatus.READY.value: 1,
        VariantStatus.GENERATING.value: 2,
        VariantStatus.REJECTED.value: 3,
        VariantStatus.FAILED.value: 4,
    }

    def _sort_key(a: Any) -> tuple[int, float]:
        prov = a.provenance or {}
        st = prov.get("variant_status", VariantStatus.READY.value)
        order = status_order.get(st, 9)
        ts = a.created_at.timestamp() if a.created_at else 0.0
        return (order, -ts)

    return sorted(variants, key=_sort_key)


def compute_variant_filename(base_prefix: str, variant_type: VariantType | str, custom_color: str | None = None) -> str:
    """Compute a clean filename for inclusion in the customer ZIP bundle."""
    vt = variant_type.value if isinstance(variant_type, VariantType) else str(variant_type)
    if vt == VariantType.DARK_SHIRT.value:
        type_suffix = "Dark_Shirt"
    elif vt == VariantType.LIGHT_SHIRT.value:
        type_suffix = "Light_Shirt"
    elif vt == VariantType.BLACK_ACCENT.value:
        type_suffix = "Black_Accent"
    elif vt == VariantType.WHITE_ACCENT.value:
        type_suffix = "White_Accent"
    elif vt == VariantType.CUSTOM.value:
        clean_hex = sanitize_hex_color(custom_color).replace("#", "")
        type_suffix = f"Custom_{clean_hex}"
    else:
        type_suffix = "Variant"

    return f"{base_prefix}_PNG_{type_suffix}.png"
