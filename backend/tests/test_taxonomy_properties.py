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
                "supports_attributes": True,
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
                "supports_attributes": True,
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
                "supports_attributes": True,
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
                "supports_attributes": True,
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
                "supports_attributes": True,
                "is_multivalued": True,
                "possible_values": [{"value_id": 1, "name": "Sublimation"}],
            },
            {
                "property_id": 82732,
                "name": "Holiday",
                "is_required": False,
                "supports_attributes": True,
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
            display_name="Craft",
            is_required=False,
            supports_attributes=True,
            supports_variations=False,
            is_multivalued=True,
            max_values_allowed=5,
            possible_values=(val,),
        )
        assert prop.property_id == 513
        assert prop.supports_attributes is True
        assert prop.display_name == "Craft"
        d = prop.to_dict()
        assert d["display_name"] == "Craft"
        assert d["supports_variations"] is False

    def test_listing_attribute_eligibility_and_variation_filtering(self):
        """Tests that is_listing_attribute_property strictly requires supports_attributes=True."""
        from app.domain.taxonomy_properties import (
            filter_listing_attribute_properties,
            is_listing_attribute_property,
        )

        prop_a = {
            "property_id": 1,
            "name": "Materials",
            "supports_attributes": True,
            "supports_variations": False,
            "possible_values": [{"value_id": 10, "name": "Canvas"}],
        }
        prop_b_variation_only = {
            "property_id": 2,
            "name": "TeeShirtSize",
            "supports_attributes": False,
            "supports_variations": True,
            "possible_values": [{"value_id": 20, "name": "XL"}],
        }
        prop_c_non_attribute = {
            "property_id": 3,
            "name": "Device",
            "supports_attributes": False,
            "supports_variations": False,
            "possible_values": [{"value_id": 30, "name": "iPad"}],
        }

        assert is_listing_attribute_property(prop_a) is True
        assert is_listing_attribute_property(prop_b_variation_only) is False
        assert is_listing_attribute_property(prop_c_non_attribute) is False

        filtered = filter_listing_attribute_properties([prop_a, prop_b_variation_only, prop_c_non_attribute])
        assert len(filtered) == 1
        assert filtered[0]["property_id"] == 1

    def test_revalidate_drops_variation_only_and_stale_properties(self):
        """Revalidation purges TeeShirtSize (100) and Device (515) and variation-only properties."""
        saved_props = {
            "100": {"property_id": 100, "value_ids": [1166], "values": ["XS"]},
            "515": {"property_id": 515, "value_ids": [5668], "values": ["iPad Mini"]},
            "513": {"property_id": 513, "value_ids": [1], "values": ["Custom Variation"]},
            "148789511893": {"property_id": 148789511893, "value_ids": [5300], "values": ["Alabaster"]},
        }

        taxonomy_props = [
            {
                "property_id": 148789511893,
                "name": "Material multi",
                "display_name": "Materials",
                "supports_attributes": True,
                "supports_variations": False,
                "is_multivalued": True,
                "max_values_allowed": 5,
                "possible_values": [
                    {"value_id": 5300, "name": "Alabaster"},
                    {"value_id": 55, "name": "Aluminum"},
                ],
            },
            {
                "property_id": 513,
                "name": "Custom1",
                "display_name": "Custom Property",
                "supports_attributes": False,
                "supports_variations": True,
                "possible_values": [{"value_id": 1, "name": "Custom Variation"}],
            },
        ]

        revalidated = revalidate_listing_taxonomy_properties(
            existing_properties=saved_props,
            available_properties=taxonomy_props,
        )

        assert "148789511893" in revalidated
        assert revalidated["148789511893"]["property_name"] == "Materials"
        assert revalidated["148789511893"]["values"] == ["Alabaster"]

        # 100, 515, 513 must all be dropped!
        assert "100" not in revalidated
        assert "515" not in revalidated
        assert "513" not in revalidated

    def test_measurement_scale_property_revalidation(self):
        """Tests that measurement properties with scales (Width/Height) are preserved and validated."""
        saved_props = {
            "47626759898": {
                "property_id": 47626759898,
                "scale_id": 5,
                "value": "15",
            },
            "47626759834": {
                "property_id": 47626759834,
                "scale_id": 999,  # invalid scale
                "value": "18",
            },
        }

        taxonomy_props = [
            {
                "property_id": 47626759898,
                "name": "Width",
                "display_name": "Width",
                "supports_attributes": True,
                "supports_variations": True,
                "scales": [
                    {"scale_id": 5, "display_name": "Inches"},
                    {"scale_id": 7, "display_name": "Centimeters"},
                ],
                "possible_values": [],
            },
            {
                "property_id": 47626759834,
                "name": "Height",
                "display_name": "Height",
                "supports_attributes": True,
                "supports_variations": True,
                "scales": [
                    {"scale_id": 5, "display_name": "Inches"},
                    {"scale_id": 7, "display_name": "Centimeters"},
                ],
                "possible_values": [],
            },
        ]

        revalidated = revalidate_listing_taxonomy_properties(
            existing_properties=saved_props,
            available_properties=taxonomy_props,
        )

        assert "47626759898" in revalidated
        assert revalidated["47626759898"]["value"] == "15"
        assert revalidated["47626759898"]["scale_name"] == "Inches"

        # Invalid scale_id 999 must be dropped
        assert "47626759834" not in revalidated

    def test_max_values_allowed_truncation(self):
        """Tests that selections are truncated to max_values_allowed if specified."""
        saved_props = {
            "400394338806": {
                "property_id": 400394338806,
                "value_ids": [10, 11, 12, 13, 14],
                "values": ["Animals", "Botanical", "Abstract", "Fantasy", "Food"],
            }
        }

        taxonomy_props = [
            {
                "property_id": 400394338806,
                "name": "Art subject",
                "display_name": "Subject",
                "supports_attributes": True,
                "is_multivalued": True,
                "max_values_allowed": 3,
                "possible_values": [
                    {"value_id": 10, "name": "Animals"},
                    {"value_id": 11, "name": "Botanical"},
                    {"value_id": 12, "name": "Abstract"},
                    {"value_id": 13, "name": "Fantasy"},
                    {"value_id": 14, "name": "Food"},
                ],
            }
        ]

        revalidated = revalidate_listing_taxonomy_properties(
            existing_properties=saved_props,
            available_properties=taxonomy_props,
        )

        assert len(revalidated["400394338806"]["values"]) == 3
        assert revalidated["400394338806"]["values"] == ["Animals", "Botanical", "Abstract"]

