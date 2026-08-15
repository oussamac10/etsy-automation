"""Centralized product mapping catalog for realistic Printful mockups.

This module isolates Printful-specific product IDs, variant IDs, and placements,
preventing hard-coded assumptions from leaking into application logic or workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True)
class VisibleZone:
    min_x: int = 900
    max_x: int = 1800
    min_y: int = 50
    max_y: int = 1000
    target_center_x: int = 1350
    target_center_y: int = 525


@dataclass(frozen=True)
class MugPlacementConfig:
    layout_mode: str = "front_focus"  # "front_focus" | "dual_sided" | "full_wrap"
    visible_zone: VisibleZone = VisibleZone()
    scale: float = 0.88
    safe_margin_px: int = 50
    horizontal_offset: int = 0
    vertical_offset: int = 0
    canvas_width: int = 2700
    canvas_height: int = 1050
    requires_wrap_canvas: bool = True


@dataclass(frozen=True)
class MockupColorVariant:
    name: str
    label: str
    hex_color: str
    variant_id: int


@dataclass(frozen=True)
class MockupProductConfig:
    product_type: str
    display_name: str
    provider: str
    product_id: int
    variant_ids: list[int]
    placement: str
    area_width: int = 1800
    area_height: int = 2400
    pos_width: int = 1800
    pos_height: int = 2400
    pos_top: int = 0
    pos_left: int = 0
    format: str = "jpg"
    mug_placement: MugPlacementConfig | None = None
    colors: tuple[MockupColorVariant, ...] = ()


@dataclass(frozen=True)
class MockupPlacementQAResult:
    passed: bool
    product_type: str
    placement_box: tuple[int, int, int, int]  # (left, top, width, height)
    center: tuple[float, float]
    target_center: tuple[float, float]
    center_offset_x: float
    center_offset_y: float
    is_inside_visible_zone: bool
    is_scale_reasonable: bool
    aspect_ratio: float
    error_message: str | None = None


def validate_mug_placement_geometry(
    artwork_width: int,
    artwork_height: int,
    config: MugPlacementConfig | None = None,
) -> tuple[MockupPlacementQAResult, tuple[int, int, int, int]]:
    """Deterministic geometric QA validation for mug mockup placement."""
    cfg = config or MugPlacementConfig()
    vz = cfg.visible_zone

    target_max_h = int((cfg.canvas_height - cfg.safe_margin_px * 2) * cfg.scale)
    target_max_w = int((vz.max_x - vz.min_x) * cfg.scale)

    aspect = artwork_width / max(1, artwork_height)
    if aspect <= (target_max_w / target_max_h):
        box_h = min(target_max_h, cfg.canvas_height - cfg.safe_margin_px * 2)
        box_w = int(box_h * aspect)
    else:
        box_w = min(target_max_w, vz.max_x - vz.min_x)
        box_h = int(box_w / aspect)

    left = int(vz.target_center_x - box_w / 2 + cfg.horizontal_offset)
    top = int(vz.target_center_y - box_h / 2 + cfg.vertical_offset)

    center_x = left + box_w / 2
    center_y = top + box_h / 2

    offset_x = abs(center_x - vz.target_center_x)
    offset_y = abs(center_y - vz.target_center_y)

    inside_vz = (
        left >= vz.min_x
        and (left + box_w) <= vz.max_x
        and top >= vz.min_y
        and (top + box_h) <= vz.max_y
    )

    scale_ratio = box_h / max(1, cfg.canvas_height)
    scale_reasonable = 0.4 <= scale_ratio <= 0.95

    passed = inside_vz and scale_reasonable and offset_x <= 20 and offset_y <= 20
    err = None if passed else "Mug placement geometry failed safe bounds or centering constraints"

    qa_res = MockupPlacementQAResult(
        passed=passed,
        product_type="mug",
        placement_box=(left, top, box_w, box_h),
        center=(center_x, center_y),
        target_center=(float(vz.target_center_x), float(vz.target_center_y)),
        center_offset_x=offset_x,
        center_offset_y=offset_y,
        is_inside_visible_zone=inside_vz,
        is_scale_reasonable=scale_reasonable,
        aspect_ratio=round(aspect, 4),
        error_message=err,
    )
    return qa_res, (left, top, box_w, box_h)


#: Centralized Printful catalog definitions for initial supported products.
MOCKUP_CATALOG: dict[str, MockupProductConfig] = {
    "tshirt": MockupProductConfig(
        product_type="tshirt",
        display_name="Unisex Staple T-Shirt (Bella + Canvas 3001)",
        provider="printful",
        product_id=71,
        variant_ids=[9575, 4011, 4012, 10528],
        placement="front",
        area_width=1800,
        area_height=2400,
        pos_width=1800,
        pos_height=2160,
        pos_top=84,
        pos_left=0,
        format="jpg",
        colors=(
            MockupColorVariant(name="white", label="White", hex_color="#FFFFFF", variant_id=9575),
            MockupColorVariant(name="black", label="Black", hex_color="#18181B", variant_id=4011),
            MockupColorVariant(name="heather_gray", label="Heather Gray", hex_color="#D1D5DB", variant_id=4012),
            MockupColorVariant(name="sand", label="Sand / Soft Cream", hex_color="#E7DECD", variant_id=10528),
        ),
    ),
    "sweatshirt": MockupProductConfig(
        product_type="sweatshirt",
        display_name="Unisex Heavy Blend Crewneck Sweatshirt (Gildan 18000)",
        provider="printful",
        product_id=145,
        variant_ids=[5434, 5435, 5437, 12948],
        placement="front",
        area_width=1800,
        area_height=2400,
        pos_width=1800,
        pos_height=2160,
        pos_top=84,
        pos_left=0,
        format="jpg",
        colors=(
            MockupColorVariant(name="white", label="White", hex_color="#FFFFFF", variant_id=5434),
            MockupColorVariant(name="black", label="Black", hex_color="#18181B", variant_id=5435),
            MockupColorVariant(name="dark_heather", label="Dark Heather", hex_color="#4B5563", variant_id=5437),
            MockupColorVariant(name="sand", label="Sand", hex_color="#D4C8B5", variant_id=12948),
        ),
    ),
    "tote_bag": MockupProductConfig(
        product_type="tote_bag",
        display_name="Large Eco Tote Bag (Econscious EC8001)",
        provider="printful",
        product_id=378,
        variant_ids=[10732, 10733],
        placement="front",
        area_width=1500,
        area_height=1500,
        pos_width=1250,
        pos_height=1500,
        pos_top=0,
        pos_left=125,
        format="jpg",
        colors=(
            MockupColorVariant(name="natural", label="Natural", hex_color="#F5F5DC", variant_id=10732),
            MockupColorVariant(name="black", label="Black", hex_color="#18181B", variant_id=10733),
        ),
    ),
    "mug": MockupProductConfig(
        product_type="mug",
        display_name="White Glossy Mug 11oz",
        provider="printful",
        product_id=19,
        variant_ids=[1320, 1321],
        placement="default",
        area_width=2700,
        area_height=1050,
        pos_width=2700,
        pos_height=1050,
        pos_top=0,
        pos_left=0,
        format="jpg",
        mug_placement=MugPlacementConfig(
            layout_mode="front_focus",
            visible_zone=VisibleZone(
                min_x=900,
                max_x=1800,
                min_y=50,
                max_y=1000,
                target_center_x=1350,
                target_center_y=525,
            ),
            scale=0.88,
            safe_margin_px=50,
            horizontal_offset=0,
            vertical_offset=0,
            canvas_width=2700,
            canvas_height=1050,
            requires_wrap_canvas=True,
        ),
        colors=(
            MockupColorVariant(name="white", label="White", hex_color="#FFFFFF", variant_id=1320),
            MockupColorVariant(name="black", label="Black", hex_color="#18181B", variant_id=1321),
        ),
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
}


def normalize_mockup_product(raw: str | None) -> str | None:
    """Normalize user input or alias to canonical product type."""
    if not raw:
        return None
    cleaned = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if cleaned in MOCKUP_CATALOG:
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
        if canonical and canonical in MOCKUP_CATALOG and canonical not in seen:
            matched.append(canonical)
            seen.add(canonical)

    if not matched:
        return list(DEFAULT_SUPPORTED_PRODUCTS)

    return matched


def get_product_config(product_type: str) -> MockupProductConfig:
    """Get configuration for a canonical product type, or raise ValueError."""
    canonical = normalize_mockup_product(product_type)
    if not canonical or canonical not in MOCKUP_CATALOG:
        raise ValueError(f"Unsupported mockup product type: {product_type}")
    return MOCKUP_CATALOG[canonical]


def get_product_colors(product_type: str) -> tuple[MockupColorVariant, ...]:
    """Return available color variants for a product type."""
    config = get_product_config(product_type)
    return config.colors


def get_variant_id_for_color(product_type: str, color_name: str | None) -> int | None:
    """Get specific variant ID for a product color or return default."""
    config = get_product_config(product_type)
    if not color_name:
        return config.variant_ids[0] if config.variant_ids else None
    target = color_name.strip().lower().replace("-", "_").replace(" ", "_")
    for c in config.colors:
        if c.name.lower() == target or c.label.lower() == target:
            return c.variant_id
    return config.variant_ids[0] if config.variant_ids else None

