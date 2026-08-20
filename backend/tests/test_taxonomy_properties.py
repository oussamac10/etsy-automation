"""Tests for Phase 9 Etsy taxonomy property discovery, validation, and category revalidation (manual-only)."""

from app.domain.taxonomy_properties import (
    TaxonomyPropertyDefinition,
    TaxonomyPropertyValue,
    check_required_taxonomy_properties,
    revalidate_listing_taxonomy_properties,
)


class TestTaxonomyProperties:
    def test_category_change_revalidation_preserves_valid_and_drops_invalid(self):
        """Category change preserves allowed selections, drops stale properties, and never auto-selects."""
        old_attributes = {
            "91001": {"property_id": 91001, "value_ids": [81001], "values": ["Sublimation"]},
            "99999": {"property_id": 99999, "value_ids": [123], "values": ["Obsolete Property"]},
        }

        new_category_props = [
            {
                "property_id": 91001,
                "name": "Craft type",
                "is_required": True,
                "is_multivalued": True,
                "possible_values": [
                    {"value_id": 81001, "name": "Sublimation"},
                    {"value_id": 81002, "name": "Printing & printmaking"},
                ],
            },
            {
                "property_id": 91002,
                "name": "Holiday",
                "is_required": False,
                "is_multivalued": False,
                "possible_values": [
                    {"value_id": 82001, "name": "Christmas"},
                    {"value_id": 82002, "name": "Halloween"},
                ],
            },
        ]

        revalidated = revalidate_listing_taxonomy_properties(
            existing_properties=old_attributes,
            available_properties=new_category_props,
        )

        # 91001 is preserved because Sublimation is valid in new category
        assert "91001" in revalidated
        assert revalidated["91001"]["values"] == ["Sublimation"]

        # 99999 is dropped because it does not exist in new category
        assert "99999" not in revalidated

        # 91002 is NOT auto-selected (no fallback, no auto-filling)
        assert "91002" not in revalidated

    def test_category_change_drops_invalid_value_in_existing_property(self):
        """If a property exists in the new category but a previously chosen value is no longer valid, drop that value."""
        old_attributes = {
            "91001": {"property_id": 91001, "value_ids": [99999], "values": ["Disallowed Value"]},
        }
        new_category_props = [
            {
                "property_id": 91001,
                "name": "Craft type",
                "is_required": False,
                "is_multivalued": True,
                "possible_values": [
                    {"value_id": 81001, "name": "Sublimation"},
                ],
            }
        ]

        revalidated = revalidate_listing_taxonomy_properties(
            existing_properties=old_attributes,
            available_properties=new_category_props,
        )
        assert "91001" not in revalidated

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

    def test_check_required_taxonomy_properties(self):
        """Verifies that missing required properties are flagged, and optional properties are ignored."""
        category_props = [
            {
                "property_id": 82731,
                "name": "Craft type",
                "is_required": True,
                "is_multivalued": True,
                "possible_values": [{"value_id": 1, "name": "Sublimation"}],
            },
            {
                "property_id": 82732,
                "name": "Holiday",
                "is_required": False,
                "is_multivalued": False,
                "possible_values": [{"value_id": 2, "name": "Christmas"}],
            },
        ]

        # 1. When empty: Craft type is required and missing
        missing = check_required_taxonomy_properties({}, category_props)
        assert missing == ["Craft type"]

        # 2. When Craft type is selected: no missing required properties
        saved = {
            "82731": {"property_id": 82731, "value_ids": [1], "values": ["Sublimation"]},
        }
        missing_after = check_required_taxonomy_properties(saved, category_props)
        assert missing_after == []

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
