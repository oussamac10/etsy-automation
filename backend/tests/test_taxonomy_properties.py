"""Tests for Phase 9 Etsy taxonomy property discovery, dynamic attributes, confidence, and revalidation."""

from app.domain.taxonomy_properties import (
    FAKE_TEST_TAXONOMY_PROPERTIES,
    TaxonomyPropertyDefinition,
    TaxonomyPropertyValue,
    revalidate_listing_taxonomy_properties,
    suggest_taxonomy_properties,
)


class TestTaxonomyProperties:
    def test_dynamic_property_ids(self):
        """Proves production logic operates on dynamic Etsy IDs, not hardcoded 513/514/515."""
        dynamic_props = [
            {
                "property_id": 82173,
                "name": "Craft type",
                "is_required": False,
                "is_multivalued": True,
                "possible_values": [
                    {"value_id": 44102, "name": "Sublimation"},
                    {"value_id": 44103, "name": "Printing & printmaking"},
                ],
            },
            {
                "property_id": 99881,
                "name": "Holiday",
                "is_required": False,
                "is_multivalued": False,
                "possible_values": [
                    {"value_id": 77110, "name": "Christmas"},
                    {"value_id": 77111, "name": "Halloween"},
                ],
            },
        ]

        suggested = suggest_taxonomy_properties(
            title="Retro Christmas Baking PNG Sublimation Clipart",
            description="High quality PNG design for heat press and crafts.",
            tags=["digital art", "sublimation file"],
            available_properties=dynamic_props,
        )

        assert "82173" in suggested
        assert 44102 in suggested["82173"]["value_ids"]
        assert "Sublimation" in suggested["82173"]["values"]
        assert suggested["82173"]["confidence"] >= 0.80

        assert "99881" in suggested
        assert 77110 in suggested["99881"]["value_ids"]
        assert "Christmas" in suggested["99881"]["values"]

    def test_no_first_value_fallback_when_unmatched(self):
        """Rule A3: When no confident match exists, property MUST be left empty."""
        props = [
            {
                "property_id": 88100,
                "name": "Holiday",
                "is_required": False,
                "is_multivalued": False,
                "possible_values": [
                    {"value_id": 11, "name": "Easter"},
                    {"value_id": 12, "name": "Halloween"},
                ],
            }
        ]
        # Title has no mention of Easter or Halloween
        suggested = suggest_taxonomy_properties(
            title="Vintage Mushroom Floral Sublimation PNG",
            description="Cottagecore design for mugs.",
            tags=["mushroom", "floral"],
            available_properties=props,
        )
        assert "88100" not in suggested

    def test_category_change_revalidation(self):
        """Rule A6: Category change strips invalid properties and keeps allowed values."""
        old_attributes = {
            "91001": {"property_id": 91001, "value_ids": [81001], "values": ["Sublimation"]},
            "99999": {"property_id": 99999, "value_ids": [123], "values": ["Obsolete Property"]},
        }

        new_category_props = [
            {
                "property_id": 91001,
                "name": "Craft type",
                "is_required": False,
                "is_multivalued": True,
                "possible_values": [
                    {"value_id": 81001, "name": "Sublimation"},
                    {"value_id": 81002, "name": "Printing & printmaking"},
                ],
            }
        ]

        revalidated = revalidate_listing_taxonomy_properties(
            existing_properties=old_attributes,
            available_properties=new_category_props,
            title="Vintage Christmas Mug Sublimation PNG",
        )

        assert "91001" in revalidated
        assert revalidated["91001"]["values"] == ["Sublimation"]
        # Stale property 99999 must be removed
        assert "99999" not in revalidated

    def test_single_valued_property_truncation(self):
        """Ensures single-valued properties cannot store multiple values."""
        invalid_multi = {
            "91002": {"property_id": 91002, "value_ids": [82001, 82002], "values": ["Christmas", "Halloween"]}
        }
        category_props = [
            {
                "property_id": 91002,
                "name": "Holiday",
                "is_required": False,
                "is_multivalued": False,
                "possible_values": [
                    {"value_id": 82001, "name": "Christmas"},
                    {"value_id": 82002, "name": "Halloween"},
                ],
            }
        ]
        revalidated = revalidate_listing_taxonomy_properties(
            existing_properties=invalid_multi,
            available_properties=category_props,
        )
        assert len(revalidated["91002"]["values"]) == 1
        assert revalidated["91002"]["values"] == ["Christmas"]

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
