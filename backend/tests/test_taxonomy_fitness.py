"""Unit tests for Etsy Taxonomy & Property Fitness Evaluation Engine."""

from __future__ import annotations

import pytest

from app.domain.taxonomy_fitness import (
    TaxonomyFitResult,
    evaluate_taxonomy_fit,
    is_physical_disqualified,
)
from app.ports.providers import EtsyTaxonomyNode, EtsyTaxonomyProperty


@pytest.fixture
def clip_art_node() -> EtsyTaxonomyNode:
    return EtsyTaxonomyNode(
        id=6844,
        level=3,
        name="Clip Art & Image Files",
        full_path="Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files",
    )


@pytest.fixture
def digital_graphic_node() -> EtsyTaxonomyNode:
    return EtsyTaxonomyNode(
        id=99001,
        level=3,
        name="Digital Graphics & Sublimation Files",
        full_path="Art & Collectibles > Drawing & Illustration > Digital Graphics & Sublimation Files",
    )


@pytest.fixture
def physical_plates_node() -> EtsyTaxonomyNode:
    return EtsyTaxonomyNode(
        id=1049,
        level=2,
        name="Plates",
        full_path="Home & Living > Kitchen & Dining > Plates",
    )


@pytest.fixture
def paper_only_properties() -> list[EtsyTaxonomyProperty]:
    return [
        EtsyTaxonomyProperty(
            property_id=82731,
            name="Craft type",
            is_required=True,
            supports_attributes=True,
            is_multivalued=True,
            possible_values=[
                {"value_id": 101, "name": "Card making & stationery"},
                {"value_id": 102, "name": "Collage"},
                {"value_id": 103, "name": "Kids' crafts"},
                {"value_id": 104, "name": "Scrapbooking"},
            ],
        ),
    ]


@pytest.fixture
def printing_sublimation_properties() -> list[EtsyTaxonomyProperty]:
    return [
        EtsyTaxonomyProperty(
            property_id=82731,
            name="Craft type",
            is_required=True,
            supports_attributes=True,
            is_multivalued=True,
            possible_values=[
                {"value_id": 201, "name": "Printing & printmaking"},
                {"value_id": 202, "name": "Sublimation"},
                {"value_id": 203, "name": "Fabric printing"},
                {"value_id": 204, "name": "Heat transfer"},
            ],
        ),
        EtsyTaxonomyProperty(
            property_id=200,
            name="Primary color",
            is_required=False,
            supports_attributes=True,
            is_multivalued=False,
            possible_values=[
                {"value_id": 301, "name": "Black"},
                {"value_id": 302, "name": "White"},
            ],
        ),
    ]


class TestTaxonomyFitness:
    """Test suite for evaluate_taxonomy_fit."""

    def test_sublimation_campaign_penalizes_paper_only_required_craft_type(
        self,
        clip_art_node: EtsyTaxonomyNode,
        paper_only_properties: list[EtsyTaxonomyProperty],
    ) -> None:
        campaign = {
            "title": "Vintage Retro Mushroom PNG Sublimation T-shirt Design",
            "description": "High resolution transparent PNG for shirts, mugs, and sublimation printing.",
            "tags": ["sublimation shirt", "tshirt graphic", "dtg transfer", "transparent png"],
            "product_type": "digital_png",
            "intended_product_uses": ["t_shirt", "sweatshirt", "sublimation", "pod"],
        }

        fit = evaluate_taxonomy_fit(
            taxonomy_node=clip_art_node,
            taxonomy_properties=paper_only_properties,
            campaign_context=campaign,
        )

        assert fit.has_mismatched_required_attributes is True
        assert fit.score <= 0.45
        assert any("paper/collage" in w.lower() for w in fit.warnings)
        assert fit.mismatched_required_reason is not None
        assert "paper/collage" in fit.mismatched_required_reason.lower()

    def test_sublimation_campaign_boosts_printing_sublimation_category(
        self,
        digital_graphic_node: EtsyTaxonomyNode,
        printing_sublimation_properties: list[EtsyTaxonomyProperty],
    ) -> None:
        campaign = {
            "title": "Vintage Retro Mushroom PNG Sublimation T-shirt Design",
            "description": "High resolution transparent PNG for shirts, mugs, and sublimation printing.",
            "tags": ["sublimation shirt", "tshirt graphic", "dtg transfer", "transparent png"],
            "product_type": "digital_png",
            "intended_product_uses": ["t_shirt", "sweatshirt", "sublimation", "pod"],
        }

        fit = evaluate_taxonomy_fit(
            taxonomy_node=digital_graphic_node,
            taxonomy_properties=printing_sublimation_properties,
            campaign_context=campaign,
        )

        assert fit.has_mismatched_required_attributes is False
        assert fit.score >= 0.85
        assert any("sublimation and printing" in r.lower() for r in fit.reasons)
        assert len(fit.warnings) == 0

    def test_scrapbooking_campaign_prefers_paper_craft_category(
        self,
        clip_art_node: EtsyTaxonomyNode,
        paper_only_properties: list[EtsyTaxonomyProperty],
    ) -> None:
        campaign = {
            "title": "Vintage Victorian Scrapbook Ephemera Paper Clipart",
            "description": "Digital junk journal paper craft elements and card making kit.",
            "tags": ["scrapbooking", "paper craft", "junk journal", "card making", "ephemera"],
            "product_type": "digital_png",
            "intended_product_uses": ["scrapbooking", "card_making", "paper_craft"],
        }

        fit = evaluate_taxonomy_fit(
            taxonomy_node=clip_art_node,
            taxonomy_properties=paper_only_properties,
            campaign_context=campaign,
        )

        assert fit.has_mismatched_required_attributes is False
        assert fit.score >= 0.85
        assert any("scrapbooking and papercraft" in r.lower() for r in fit.reasons)

    def test_physical_category_disqualified(
        self,
        physical_plates_node: EtsyTaxonomyNode,
    ) -> None:
        campaign = {
            "title": "Retro Mushroom Graphic Plate Design",
            "tags": ["plate", "dish", "sublimation"],
        }

        fit = evaluate_taxonomy_fit(
            taxonomy_node=physical_plates_node,
            taxonomy_properties=[],
            campaign_context=campaign,
        )

        assert is_physical_disqualified(physical_plates_node.full_path) is True
        assert fit.score == 0.0
        assert fit.has_mismatched_required_attributes is True
        assert any("disqualified" in w.lower() for w in fit.warnings)

    def test_dynamic_arbitrary_ids_evaluated_without_hardcoding(self) -> None:
        custom_node = EtsyTaxonomyNode(
            id=54321,
            level=2,
            name="Apparel Graphics & Heat Transfer",
            full_path="Craft Supplies & Tools > Fabric & Sewing > Apparel Graphics & Heat Transfer",
        )
        custom_props = [
            EtsyTaxonomyProperty(
                property_id=999,
                name="Craft type",
                is_required=True,
                supports_attributes=True,
                is_multivalued=True,
                possible_values=[{"value_id": 1, "name": "Heat transfer"}, {"value_id": 2, "name": "Sublimation"}],
            )
        ]
        campaign = {
            "title": "Streetwear Hoodie Graphic PNG",
            "tags": ["hoodie", "sublimation", "heat transfer"],
            "intended_product_uses": ["t_shirt", "hoodie"],
        }

        fit = evaluate_taxonomy_fit(
            taxonomy_node=custom_node,
            taxonomy_properties=custom_props,
            campaign_context=campaign,
        )

        assert fit.score >= 0.80
        assert fit.has_mismatched_required_attributes is False
