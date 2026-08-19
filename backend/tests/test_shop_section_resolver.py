"""Tests for Phase 9 Etsy shop section resolution and organization."""

from app.domain.shop_section_resolver import (
    find_matching_existing_section,
    normalize_section_title,
    suggest_shop_section_title,
)


class TestShopSectionResolver:
    def test_normalize_section_title(self):
        assert normalize_section_title("  christmas   pngs  ") == "Christmas Pngs"
        assert normalize_section_title("sublimation bundles") == "Sublimation Bundles"

    def test_suggest_shop_section_title_christmas(self):
        title = "Retro Christmas Baking Cookies Sublimation PNG"
        tags = ["christmas baking", "gingerbread man", "holiday clipart"]
        suggested, matched_id = suggest_shop_section_title(title=title, tags=tags)
        assert suggested == "Christmas PNGs"
        assert matched_id is None

    def test_suggest_shop_section_title_fall(self):
        title = "Aesthetic Fall Autumn Cozy Design"
        tags = ["fall vibes", "autumn aesthetic", "cozy harvest"]
        suggested, matched_id = suggest_shop_section_title(title=title, tags=tags)
        assert suggested == "Fall PNGs"

    def test_find_matching_existing_section(self):
        existing_sections = [
            {"shop_section_id": "101", "title": "Christmas PNGs"},
            {"shop_section_id": "102", "title": "Sublimation Bundles"},
        ]

        # Exact match
        sec_id, sec_title = find_matching_existing_section(
            suggested_title="Christmas PNGs", existing_sections=existing_sections
        )
        assert sec_id == "101"
        assert sec_title == "Christmas PNGs"

        # Fuzzy / lowercase match
        sec_id_fuzz, _ = find_matching_existing_section(
            suggested_title="Sublimation Bundles", existing_sections=existing_sections
        )
        assert sec_id_fuzz == "102"

        # No match
        no_id, _ = find_matching_existing_section(
            suggested_title="Halloween Spooky", existing_sections=existing_sections
        )
        assert no_id is None
