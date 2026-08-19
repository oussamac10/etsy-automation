"""Tests for Phase 9 Etsy taxonomy property discovery and attributes."""

from app.domain.taxonomy_properties import (
    STANDARD_DIGITAL_PROPERTIES,
    TaxonomyPropertyDefinition,
    TaxonomyPropertyValue,
    suggest_taxonomy_properties,
)


class TestTaxonomyProperties:
    def test_suggest_craft_type(self):
        suggested = suggest_taxonomy_properties(
            title="Retro Christmas Baking PNG Sublimation Clipart",
            description="High quality PNG design for heat press and crafts.",
            tags=["digital art", "sublimation file"],
        )
        assert "513" in suggested
        assert "Sublimation" in suggested["513"]["values"]

    def test_suggest_holiday(self):
        suggested = suggest_taxonomy_properties(
            title="Gingerbread Cookies Holiday Baking PNG",
            description="Cozy holiday art for Christmas.",
            tags=["christmas", "xmas decor"],
        )
        assert "514" in suggested
        assert "Christmas" in suggested["514"]["values"]

    def test_suggest_season(self):
        suggested = suggest_taxonomy_properties(
            title="Aesthetic Pumpkin Patch Autumn Artwork",
            description="Cozy fall vibes.",
            tags=["fall", "pumpkin"],
        )
        assert "515" in suggested
        assert "Autumn" in suggested["515"]["values"]

    def test_taxonomy_property_dataclasses(self):
        val = TaxonomyPropertyValue(value_id=1, name="Sublimation")
        assert val.value_id == 1
        assert val.name == "Sublimation"

        prop = TaxonomyPropertyDefinition(
            property_id=513,
            name="Craft type",
            is_required=False,
            supports_attributes=True,
            is_multivalued=True,
            possible_values=(val,),
        )
        assert prop.property_id == 513
        assert prop.supports_attributes is True
