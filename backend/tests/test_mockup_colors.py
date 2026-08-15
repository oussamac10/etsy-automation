import pytest
from app.infrastructure.mockup_catalog import (
    MOCKUP_CATALOG,
    get_product_colors,
    get_variant_id_for_color,
    normalize_mockup_product,
)


def test_mockup_catalog_contains_color_variants():
    for product_type in ("tshirt", "sweatshirt", "tote_bag", "mug"):
        colors = get_product_colors(product_type)
        assert len(colors) >= 2, f"Product {product_type} should have multiple colors"
        for c in colors:
            assert c.name
            assert c.label
            assert c.hex_color.startswith("#")
            assert c.variant_id > 0


def test_variant_id_lookup():
    # T-Shirt colors
    assert get_variant_id_for_color("tshirt", "white") == 9575
    assert get_variant_id_for_color("tshirt", "black") == 4011
    assert get_variant_id_for_color("tshirt", "heather_gray") == 4012
    assert get_variant_id_for_color("tshirt", "sand") == 10528

    # Sweatshirt colors
    assert get_variant_id_for_color("sweatshirt", "white") == 5434
    assert get_variant_id_for_color("sweatshirt", "black") == 5435
    assert get_variant_id_for_color("sweatshirt", "dark_heather") == 5437
    assert get_variant_id_for_color("sweatshirt", "sand") == 12948

    # Fallback to default
    assert get_variant_id_for_color("tshirt", "unknown_color") == 9575
