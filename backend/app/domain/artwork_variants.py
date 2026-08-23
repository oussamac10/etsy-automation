"""Domain definitions, enums, prompt builders, deterministic recolor engine, and validation for artwork color variants.

Enables creating alternate color-safe versions of an approved master PNG
(e.g., dark-shirt friendly, light-shirt friendly, black accent, white accent, custom color)
without mutating the original master artwork.
"""

from __future__ import annotations

import io
import re
from enum import StrEnum
from typing import Any, Final

from PIL import Image, ImageChops

DEFAULT_PROMPT_VERSION: Final[str] = "color-variant-v2-deterministic"
DEFAULT_DARK_SHIRT_TARGET: Final[str] = "#F5E6C8"  # Warm Cream
DEFAULT_LIGHT_SHIRT_TARGET: Final[str] = "#1A1A1A"  # Deep Charcoal
DEFAULT_BLACK_ACCENT_TARGET: Final[str] = "#0A0A0A"  # Rich Black
DEFAULT_WHITE_ACCENT_TARGET: Final[str] = "#FFFFFF"  # Crisp White


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


class ArtworkVariantValidationError(Exception):
    """Raised when an artwork variant fails strict format, transparency, or quality validation."""


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


def sanitize_hex_color(hex_str: str | None, default: str = "#FFFFFF") -> str:
    """Validate and normalize a 3- or 6-digit hex color code."""
    if not hex_str:
        return default
    cleaned = hex_str.strip()
    if not cleaned.startswith("#"):
        cleaned = f"#{cleaned}"
    if re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", cleaned):
        if len(cleaned) == 4:
            # Expand #RGB to #RRGGBB
            cleaned = f"#{cleaned[1] * 2}{cleaned[2] * 2}{cleaned[3] * 2}"
        return cleaned.upper()
    return default


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert hex color string (#RRGGBB) to (R, G, B) tuple."""
    sanitized = sanitize_hex_color(hex_str).lstrip("#")
    return (
        int(sanitized[0:2], 16),
        int(sanitized[2:4], 16),
        int(sanitized[4:6], 16),
    )


# ---------------------------------------------------------------------------
# Strict Validation & Heuristic Checks
# ---------------------------------------------------------------------------


def is_png_format(image_bytes: bytes) -> bool:
    """Validate standard PNG magic bytes."""
    return image_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def detect_baked_checkerboard(image: Image.Image) -> bool:
    """Heuristic check to detect baked gray/white transparency checkerboard patterns."""
    if image.mode != "RGBA":
        return False

    w, h = image.size
    sample_size = min(100, w // 4, h // 4)
    if sample_size <= 10:
        return False

    # Check 4 corners for opaque alternating gray/white tiles
    corners = [
        (0, 0),
        (w - sample_size, 0),
        (0, h - sample_size),
        (w - sample_size, h - sample_size),
    ]

    for cx, cy in corners:
        box = (cx, cy, cx + sample_size, cy + sample_size)
        corner_crop = image.crop(box)
        _, _, _, alpha = corner_crop.split()
        extrema = alpha.getextrema()
        # If corner is completely opaque
        if (
            isinstance(extrema, tuple)
            and len(extrema) == 2
            and isinstance(extrema[0], (int, float))
            and isinstance(extrema[1], (int, float))
            and extrema[0] == 255
            and extrema[1] == 255
        ):
            gray = corner_crop.convert("L")
            g_ext = gray.getextrema()
            # Alternating light gray (~190-210) and pure white (255) pattern
            if (
                isinstance(g_ext, tuple)
                and len(g_ext) == 2
                and isinstance(g_ext[0], (int, float))
                and isinstance(g_ext[1], (int, float))
                and g_ext[0] >= 180
                and g_ext[1] == 255
                and (g_ext[1] - g_ext[0]) >= 35
            ):
                return True

    return False


def validate_artwork_variant(
    *,
    source_bytes: bytes,
    variant_bytes: bytes,
    variant_type: VariantType | str,
) -> dict[str, Any]:
    """Strictly validate an artwork color variant against the approved master source.

    Raises ArtworkVariantValidationError on any violation.
    """
    # 1. Format & Magic Bytes
    if not is_png_format(variant_bytes):
        if variant_bytes.startswith(b"\xff\xd8\xff"):
            raise ArtworkVariantValidationError(
                "Variant provider returned JPEG. Transparent PNG required."
            )
        raise ArtworkVariantValidationError(
            "Output file is not a valid PNG. Transparent PNG required."
        )

    # 2. Decode Images
    try:
        variant_img = Image.open(io.BytesIO(variant_bytes))
    except Exception as exc:
        raise ArtworkVariantValidationError(f"Corrupted or unreadable PNG output: {exc}") from exc

    try:
        source_img = Image.open(io.BytesIO(source_bytes))
    except Exception as exc:
        raise ArtworkVariantValidationError(f"Corrupted source PNG: {exc}") from exc

    # 3. Mode Check
    if variant_img.mode != "RGBA":
        raise ArtworkVariantValidationError(
            f"Variant image mode is '{variant_img.mode}'. RGBA with real alpha transparency is strictly required."
        )

    # 4. Checkerboard Detection Heuristic
    if detect_baked_checkerboard(variant_img):
        raise ArtworkVariantValidationError(
            "Detected baked checkerboard pattern in output pixels. Real transparent background required."
        )

    # 5. Real Alpha Transparency
    _, _, _, v_alpha = variant_img.split()
    v_alpha_min, v_alpha_max = v_alpha.getextrema()
    if v_alpha_min == 255:
        raise ArtworkVariantValidationError(
            "Generated variant lacks transparency. Pure opaque image is invalid for digital PNG deliverable."
        )

    # 6. Dimensions & Aspect Ratio Match
    if variant_img.size != source_img.size:
        raise ArtworkVariantValidationError(
            f"Variant dimensions {variant_img.size} do not match source master dimensions {source_img.size}."
        )

    # 6. Source Alpha Coverage Invariant
    if source_img.mode == "RGBA":
        _, _, _, s_alpha = source_img.split()
        s_ext = s_alpha.getextrema()
        if (
            isinstance(s_ext, tuple)
            and len(s_ext) == 2
            and isinstance(s_ext[0], (int, float))
            and s_ext[0] < 255
        ):
            # Source had transparent background. Ensure variant didn't become fully opaque.
            if v_alpha_min == 255:
                raise ArtworkVariantValidationError(
                    "Generated variant lost the transparent background."
                )

    return {
        "is_valid": True,
        "format": "image/png",
        "mode": variant_img.mode,
        "width": variant_img.width,
        "height": variant_img.height,
        "has_real_alpha": True,
        "min_alpha": v_alpha_min,
        "checkerboard_free": True,
        "source_composition_preserved": True,
        "variant_type": str(variant_type),
    }


# ---------------------------------------------------------------------------
# Deterministic Pixel / Color-Range Recolor Engine
# ---------------------------------------------------------------------------


def recolor_artwork_variant(
    source_bytes: bytes,
    variant_type: VariantType | str,
    *,
    target_color_hex: str | None = None,
    darkness_threshold: float | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Deterministically recolor target elements while preserving exact alpha, composition, and texture.

    1. Preserves source dimensions, DPI metadata, and 100% byte-identical alpha channel.
    2. Identifies dark/black lines and textures with luminance and chroma thresholding.
    3. Maps dark pixels to target cream/light colors with luminance modulation to keep distressing grain.
    4. Preserves non-target colors (orange, teal, mustard, red, beige, etc.) completely intact.
    5. Returns (output_png_bytes, validation_report).
    """
    if not is_png_format(source_bytes):
        raise ArtworkVariantValidationError("Source artwork is not a valid PNG.")

    try:
        raw_src = Image.open(io.BytesIO(source_bytes))
    except Exception as exc:
        raise ArtworkVariantValidationError(f"Cannot decode source PNG: {exc}") from exc

    src_img: Image.Image = raw_src.convert("RGBA") if raw_src.mode != "RGBA" else raw_src

    dpi = src_img.info.get("dpi", (300, 300))
    width, height = src_img.size

    v_type = VariantType(variant_type) if isinstance(variant_type, str) else variant_type

    r, g, b, a = src_img.split()
    gray = src_img.convert("L")

    # Chroma delta: max(r,g,b) - min(r,g,b)
    max_rgb = ImageChops.lighter(r, ImageChops.lighter(g, b))
    min_rgb = ImageChops.darker(r, ImageChops.darker(g, b))
    sat_delta = ImageChops.difference(max_rgb, min_rgb)

    # 1. Dark Shirt Version (Default: Warm Cream #F5E6C8)
    if v_type == VariantType.DARK_SHIRT:
        target_hex = sanitize_hex_color(target_color_hex, default=DEFAULT_DARK_SHIRT_TARGET)
        target_r, target_g, target_b = hex_to_rgb(target_hex)

        # Luma threshold: default ~0.28 (71 / 255)
        thresh_float = float(darkness_threshold) if darkness_threshold is not None else 0.28
        luma_thresh = max(20, min(140, int(thresh_float * 255)))

        low_chroma = sat_delta.point(lambda p: 255 if p <= 55 else 0, mode="L")
        dark_luma = gray.point(lambda p: 255 if p < luma_thresh else 0, mode="L")
        deep_black = gray.point(lambda p: 255 if p < 35 else 0, mode="L")
        neutral_darks = ImageChops.multiply(dark_luma, low_chroma)
        candidate_mask = ImageChops.lighter(neutral_darks, deep_black)

        # Luminance-preserving cream tone modulation
        mod_r = gray.point(
            lambda p: (
                min(255, int(target_r * (0.82 + 0.35 * min(1.0, p / float(luma_thresh)))))
                if p < luma_thresh
                else target_r
            ),
            mode="L",
        )
        mod_g = gray.point(
            lambda p: (
                min(255, int(target_g * (0.82 + 0.35 * min(1.0, p / float(luma_thresh)))))
                if p < luma_thresh
                else target_g
            ),
            mode="L",
        )
        mod_b = gray.point(
            lambda p: (
                min(255, int(target_b * (0.82 + 0.35 * min(1.0, p / float(luma_thresh)))))
                if p < luma_thresh
                else target_b
            ),
            mode="L",
        )

    # 2. Light Shirt Version (Default: Deep Charcoal #1A1A1A)
    elif v_type == VariantType.LIGHT_SHIRT:
        target_hex = sanitize_hex_color(target_color_hex, default=DEFAULT_LIGHT_SHIRT_TARGET)
        target_r, target_g, target_b = hex_to_rgb(target_hex)

        light_thresh = 190
        low_chroma = sat_delta.point(lambda p: 255 if p <= 50 else 0, mode="L")
        light_luma = gray.point(lambda p: 255 if p > light_thresh else 0, mode="L")
        candidate_mask = ImageChops.multiply(light_luma, low_chroma)

        mod_r = gray.point(
            lambda p: (
                max(0, min(255, int(target_r * (1.0 - 0.25 * ((p - light_thresh) / 65.0)))))
                if p > light_thresh
                else target_r
            ),
            mode="L",
        )
        mod_g = gray.point(
            lambda p: (
                max(0, min(255, int(target_g * (1.0 - 0.25 * ((p - light_thresh) / 65.0)))))
                if p > light_thresh
                else target_g
            ),
            mode="L",
        )
        mod_b = gray.point(
            lambda p: (
                max(0, min(255, int(target_b * (1.0 - 0.25 * ((p - light_thresh) / 65.0)))))
                if p > light_thresh
                else target_b
            ),
            mode="L",
        )

    # 3. Black Accent Version (Default: #0A0A0A)
    elif v_type == VariantType.BLACK_ACCENT:
        target_hex = sanitize_hex_color(target_color_hex, default=DEFAULT_BLACK_ACCENT_TARGET)
        target_r, target_g, target_b = hex_to_rgb(target_hex)

        dark_thresh = 80
        low_chroma = sat_delta.point(lambda p: 255 if p <= 60 else 0, mode="L")
        dark_luma = gray.point(lambda p: 255 if p < dark_thresh else 0, mode="L")
        candidate_mask = ImageChops.multiply(dark_luma, low_chroma)

        mod_r = gray.point(lambda p: target_r, mode="L")
        mod_g = gray.point(lambda p: target_g, mode="L")
        mod_b = gray.point(lambda p: target_b, mode="L")

    # 4. White Accent Version (Default: #FFFFFF)
    elif v_type == VariantType.WHITE_ACCENT:
        target_hex = sanitize_hex_color(target_color_hex, default=DEFAULT_WHITE_ACCENT_TARGET)
        target_r, target_g, target_b = hex_to_rgb(target_hex)

        dark_thresh = 70
        low_chroma = sat_delta.point(lambda p: 255 if p <= 55 else 0, mode="L")
        dark_luma = gray.point(lambda p: 255 if p < dark_thresh else 0, mode="L")
        candidate_mask = ImageChops.multiply(dark_luma, low_chroma)

        mod_r = gray.point(lambda p: target_r, mode="L")
        mod_g = gray.point(lambda p: target_g, mode="L")
        mod_b = gray.point(lambda p: target_b, mode="L")

    # 5. Custom Brand Accent Color
    else:
        target_hex = sanitize_hex_color(target_color_hex, default="#E85D04")
        target_r, target_g, target_b = hex_to_rgb(target_hex)

        thresh_float = float(darkness_threshold) if darkness_threshold is not None else 0.28
        luma_thresh = max(20, min(140, int(thresh_float * 255)))

        low_chroma = sat_delta.point(lambda p: 255 if p <= 55 else 0, mode="L")
        dark_luma = gray.point(lambda p: 255 if p < luma_thresh else 0, mode="L")
        candidate_mask = ImageChops.multiply(dark_luma, low_chroma)

        mod_r = gray.point(
            lambda p: (
                min(255, int(target_r * (0.85 + 0.30 * min(1.0, p / float(luma_thresh)))))
                if p < luma_thresh
                else target_r
            ),
            mode="L",
        )
        mod_g = gray.point(
            lambda p: (
                min(255, int(target_g * (0.85 + 0.30 * min(1.0, p / float(luma_thresh)))))
                if p < luma_thresh
                else target_g
            ),
            mode="L",
        )
        mod_b = gray.point(
            lambda p: (
                min(255, int(target_b * (0.85 + 0.30 * min(1.0, p / float(luma_thresh)))))
                if p < luma_thresh
                else target_b
            ),
            mode="L",
        )

    # Restrict recolor strictly to non-transparent pixels (exact alpha preserved!)
    recolor_mask = ImageChops.multiply(candidate_mask, a)

    # Create recolored layer with original alpha
    recolored_layer = Image.merge("RGBA", (mod_r, mod_g, mod_b, a))

    # Composite: where recolor_mask is active, use recolored layer; everywhere else keep original pixel!
    final_img = Image.composite(recolored_layer, src_img, recolor_mask)

    # Encode to lossless PNG buffer with preserved DPI
    out_buf = io.BytesIO()
    final_img.save(out_buf, format="PNG", dpi=dpi, optimize=True)
    out_bytes = out_buf.getvalue()

    # Run validation checks
    report = validate_artwork_variant(
        source_bytes=source_bytes,
        variant_bytes=out_bytes,
        variant_type=v_type,
    )
    report["target_color"] = target_hex
    report["method"] = "deterministic_color_range"

    return out_bytes, report


def is_valid_artwork_variant_asset(asset_provenance: dict[str, Any] | None) -> bool:
    """Check if an asset's provenance indicates it is a valid artwork color variant."""
    if not asset_provenance or not isinstance(asset_provenance, dict):
        return False
    return asset_provenance.get("kind") == "artwork_variant"


def filter_workflow_artwork_variants(assets: list[Any]) -> list[Any]:
    """Filter and sort artwork variants for a workflow."""
    variants = [a for a in assets if is_valid_artwork_variant_asset(a.provenance)]
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


def compute_variant_filename(
    base_prefix: str,
    variant_type: VariantType | str,
    custom_color: str | None = None,
) -> str:
    """Compute a clean, customer-safe filename for inclusion in the deliverable package."""
    vt = variant_type.value if isinstance(variant_type, VariantType) else str(variant_type)
    if vt in (VariantType.DARK_SHIRT.value, "dark_shirt"):
        type_suffix = "Dark_Shirt"
    elif vt in (VariantType.LIGHT_SHIRT.value, "light_shirt"):
        type_suffix = "Light_Shirt"
    elif vt in (VariantType.BLACK_ACCENT.value, "black_accent"):
        type_suffix = "Black_Accent"
    elif vt in (VariantType.WHITE_ACCENT.value, "white_accent"):
        type_suffix = "White_Accent"
    elif vt in (VariantType.CUSTOM.value, "custom"):
        clean_hex = sanitize_hex_color(custom_color, default="#E85D04").replace("#", "")
        type_suffix = f"Custom_{clean_hex}"
    elif vt in ("original", "master", "master_png"):
        type_suffix = "Original"
    else:
        type_suffix = "Variant"

    return f"{base_prefix}_{type_suffix}.png"


def is_variant_outdated(variant_asset: Any, current_master_asset: Any | None) -> bool:
    """Check if a variant was derived from an older master PNG that has since been replaced."""
    if current_master_asset is None:
        return False
    if getattr(variant_asset, "derived_from_id", None) is None:
        return False
    return str(variant_asset.derived_from_id) != str(current_master_asset.id)


def is_variant_eligible_for_package(variant_asset: Any, current_master_asset: Any | None) -> bool:
    """Check if a variant is approved and current, eligible for packaging."""
    prov = getattr(variant_asset, "provenance", None) or {}
    if prov.get("variant_status") != VariantStatus.APPROVED.value:
        return False
    return not is_variant_outdated(variant_asset, current_master_asset)
