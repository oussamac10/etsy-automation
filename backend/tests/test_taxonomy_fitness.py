"""Unit tests for Etsy Taxonomy & Property Fitness Evaluation Engine."""

from __future__ import annotations

import pytest

from app.domain.taxonomy_fitness import (
    TaxonomyFitResult,
    evaluate_taxonomy_fit,
    evaluate_taxonomy_attribute_fit,
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

    def test_case_1_sublimation_campaign_penalizes_paper_only_required_craft_type(
        self,
        clip_art_node: EtsyTaxonomyNode,
        digital_graphic_node: EtsyTaxonomyNode,
        paper_only_properties: list[EtsyTaxonomyProperty],
        printing_sublimation_properties: list[EtsyTaxonomyProperty],
    ) -> None:
        campaign = {
            "title": "Retro Camping Dog PNG Sublimation Design",
            "description": "High resolution transparent PNG for shirts, mugs, and sublimation printing.",
            "tags": ["sublimation", "tshirt png", "pod graphics"],
            "product_type": "digital_png",
            "intended_product_uses": ["t_shirt", "sweatshirt", "sublimation"],
        }

        # Candidate A (paper-only craft types)
        fit_a = evaluate_taxonomy_attribute_fit(
            taxonomy_node=clip_art_node,
            taxonomy_properties=paper_only_properties,
            campaign_context=campaign,
        )

        assert fit_a.fit == "poor"
        assert fit_a.blocking_mismatch is True
        assert fit_a.has_mismatched_required_attributes is True
        assert fit_a.score <= 0.35
        assert fit_a.campaign_intent == "apparel_sublimation"
        assert any("paper/collage" in r.lower() for r in fit_a.reasons)
        assert any("sublimation and apparel" in r.lower() for r in fit_a.reasons)

        # Candidate B (printing & sublimation craft types)
        fit_b = evaluate_taxonomy_attribute_fit(
            taxonomy_node=digital_graphic_node,
            taxonomy_properties=printing_sublimation_properties,
            campaign_context=campaign,
        )

        assert fit_b.fit == "good"
        assert fit_b.blocking_mismatch is False
        assert fit_b.score >= 0.85
        assert fit_b.score > fit_a.score

    def test_case_2_scrapbooking_campaign_prefers_paper_craft_category(
        self,
        clip_art_node: EtsyTaxonomyNode,
        paper_only_properties: list[EtsyTaxonomyProperty],
    ) -> None:
        campaign = {
            "title": "Vintage Floral Scrapbooking PNG",
            "description": "Digital junk journal paper craft elements and card making kit.",
            "tags": ["scrapbooking", "card making", "ephemera"],
            "product_type": "digital_png",
            "intended_product_uses": ["scrapbooking", "card_making"],
        }

        fit = evaluate_taxonomy_fit(
            taxonomy_node=clip_art_node,
            taxonomy_properties=paper_only_properties,
            campaign_context=campaign,
        )

        assert fit.fit == "good"
        assert fit.blocking_mismatch is False
        assert fit.has_mismatched_required_attributes is False
        assert fit.score >= 0.85
        assert fit.campaign_intent == "scrapbooking_paper"
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
        assert fit.fit == "poor"
        assert fit.blocking_mismatch is True
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
        assert fit.fit == "good"
        assert fit.blocking_mismatch is False
        assert fit.has_mismatched_required_attributes is False

    def test_intent_classification_signals(self, clip_art_node: EtsyTaxonomyNode) -> None:
        # Wall art
        wall_art_fit = evaluate_taxonomy_fit(
            taxonomy_node=clip_art_node,
            taxonomy_properties=[],
            campaign_context={"title": "Nursery Wall Art Poster", "product_type": "digital_print"},
        )
        assert wall_art_fit.campaign_intent == "wall_art_print"

        # Illustration
        illustration_fit = evaluate_taxonomy_fit(
            taxonomy_node=clip_art_node,
            taxonomy_properties=[],
            campaign_context={"title": "Custom Cat Portrait Drawing", "product_type": "digital_drawing"},
        )
        assert illustration_fit.campaign_intent == "digital_illustration"
