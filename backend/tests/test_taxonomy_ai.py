"""Tests for AI-assisted Etsy category attributes suggestions."""

from __future__ import annotations

import uuid
import pytest
from app.domain.taxonomy_ai import (
    compute_taxonomy_content_fingerprint,
    build_taxonomy_ai_context,
    build_taxonomy_ai_prompt,
    validate_ai_taxonomy_suggestions,
    ValidatedTaxonomySuggestion,
)


@pytest.fixture
def sample_arbitrary_etsy_properties() -> list[dict[str, object]]:
    """Arbitrary Etsy property definitions (non-standard arbitrary IDs)."""
    return [
        {
            "property_id": 82731,
            "name": "Craft type",
            "is_required": True,
            "is_multivalued": True,
            "possible_values": [
                {"value_id": 441908, "name": "Sublimation"},
                {"value_id": 441909, "name": "Card making & stationery"},
                {"value_id": 441910, "name": "Printing & printmaking"},
            ],
        },
        {
            "property_id": 82732,
            "name": "Holiday",
            "is_required": False,
            "is_multivalued": False,
            "possible_values": [
                {"value_id": 551201, "name": "Christmas"},
                {"value_id": 551202, "name": "Halloween"},
                {"value_id": 551203, "name": "Easter"},
            ],
        },
        {
            "property_id": 82733,
            "name": "Primary color",
            "is_required": False,
            "is_multivalued": False,
            "possible_values": [
                {"value_id": 661001, "name": "Brown"},
                {"value_id": 661002, "name": "Red"},
                {"value_id": 661003, "name": "Green"},
            ],
        },
    ]


def test_validate_ai_taxonomy_suggestions_valid(sample_arbitrary_etsy_properties):
    """Test valid selections from arbitrary Etsy IDs."""
    raw_ai_response = {
        "selections": [
            {
                "property_id": 82731,
                "value_ids": [441908, 441910],
                "confidence": 0.95,
                "reason": "Explicitly targets sublimation design files.",
            },
            {
                "property_id": 82732,
                "value_ids": [551201],
                "confidence": 0.98,
                "reason": "Artwork is Christmas themed.",
            },
        ]
    }

    validated = validate_ai_taxonomy_suggestions(raw_ai_response, sample_arbitrary_etsy_properties)

    assert len(validated) == 2
    # Required/high confidence sorted first
    craft_prop = next(s for s in validated if s.property_id == 82731)
    assert craft_prop.property_name == "Craft type"
    assert craft_prop.value_ids == [441908, 441910]
    assert craft_prop.values == ["Sublimation", "Printing & printmaking"]
    assert craft_prop.confidence == 0.95
    assert craft_prop.is_high_confidence is True
    assert craft_prop.is_required is True
    assert craft_prop.is_multivalued is True

    holiday_prop = next(s for s in validated if s.property_id == 82732)
    assert holiday_prop.property_name == "Holiday"
    assert holiday_prop.value_ids == [551201]
    assert holiday_prop.values == ["Christmas"]
    assert holiday_prop.confidence == 0.98
    assert holiday_prop.is_high_confidence is True


def test_validate_ai_taxonomy_suggestions_rejects_hallucinations(sample_arbitrary_etsy_properties):
    """Test that unknown property IDs and value IDs are strictly dropped."""
    raw_ai_response = {
        "selections": [
            {
                # Hallucinated property ID
                "property_id": 999999,
                "value_ids": [12345],
                "confidence": 0.99,
                "reason": "Made up property.",
            },
            {
                # Valid property ID, but hallucinated value ID
                "property_id": 82732,
                "value_ids": [999999],
                "confidence": 0.90,
                "reason": "Made up value for Holiday.",
            },
            {
                # Valid property ID, 1 valid value and 1 hallucinated value
                "property_id": 82731,
                "value_ids": [441908, 999999],
                "confidence": 0.92,
                "reason": "Mixed valid and invalid values.",
            },
        ]
    }

    validated = validate_ai_taxonomy_suggestions(raw_ai_response, sample_arbitrary_etsy_properties)

    # 999999 is dropped, 82732 with invalid value is dropped, 82731 retains only valid 441908
    assert len(validated) == 1
    assert validated[0].property_id == 82731
    assert validated[0].value_ids == [441908]
    assert validated[0].values == ["Sublimation"]


def test_validate_ai_taxonomy_suggestions_enforces_single_value(sample_arbitrary_etsy_properties):
    """Test single-valued property is clamped to at most one value."""
    raw_ai_response = {
        "selections": [
            {
                # Holiday is single-valued
                "property_id": 82732,
                "value_ids": [551201, 551202],
                "confidence": 0.88,
                "reason": "AI picked both Christmas and Halloween.",
            }
        ]
    }

    validated = validate_ai_taxonomy_suggestions(raw_ai_response, sample_arbitrary_etsy_properties)

    assert len(validated) == 1
    assert validated[0].property_id == 82732
    assert len(validated[0].value_ids) == 1
    assert validated[0].value_ids == [551201]


def test_fingerprint_deterministic_and_sensitive(sample_arbitrary_etsy_properties):
    """Test content fingerprint is deterministic and invalidates on changes."""
    wf_1 = str(uuid.uuid4())
    wf_2 = str(uuid.uuid4())

    fp1 = compute_taxonomy_content_fingerprint(
        workflow_id=wf_1,
        taxonomy_id=6844,
        title="Retro Christmas Baking PNG",
        description="High resolution digital sublimation design.",
        tags=["christmas png", "sublimation shirt", "retro baking"],
        properties=sample_arbitrary_etsy_properties,
    )

    # Same inputs yield identical fingerprint
    fp1_recomputed = compute_taxonomy_content_fingerprint(
        workflow_id=wf_1,
        taxonomy_id=6844,
        title="Retro Christmas Baking PNG",
        description="High resolution digital sublimation design.",
        tags=["christmas png", "sublimation shirt", "retro baking"],
        properties=sample_arbitrary_etsy_properties,
    )
    assert fp1 == fp1_recomputed

    # Different workflow (Campaign isolation)
    fp_diff_wf = compute_taxonomy_content_fingerprint(
        workflow_id=wf_2,
        taxonomy_id=6844,
        title="Retro Christmas Baking PNG",
        description="High resolution digital sublimation design.",
        tags=["christmas png", "sublimation shirt", "retro baking"],
        properties=sample_arbitrary_etsy_properties,
    )
    assert fp1 != fp_diff_wf

    # Changed title
    fp_diff_title = compute_taxonomy_content_fingerprint(
        workflow_id=wf_1,
        taxonomy_id=6844,
        title="Cozy Fall Book Lover PNG",
        description="High resolution digital sublimation design.",
        tags=["christmas png", "sublimation shirt", "retro baking"],
        properties=sample_arbitrary_etsy_properties,
    )
    assert fp1 != fp_diff_title

    # Changed taxonomy
    fp_diff_tax = compute_taxonomy_content_fingerprint(
        workflow_id=wf_1,
        taxonomy_id=9999,
        title="Retro Christmas Baking PNG",
        description="High resolution digital sublimation design.",
        tags=["christmas png", "sublimation shirt", "retro baking"],
        properties=sample_arbitrary_etsy_properties,
    )
    assert fp1 != fp_diff_tax


def test_build_taxonomy_ai_prompt_contains_campaign_and_allowed_properties(sample_arbitrary_etsy_properties):
    """Test that context builder and prompt builder correctly include campaign data and Etsy options."""
    wf_id = str(uuid.uuid4())
    context = build_taxonomy_ai_context(
        workflow_id=wf_id,
        workflow_name="Retro Christmas Baking",
        concept_title="Retro Christmas Baking PNG",
        concept_description="Cute gingerbread baker sublimation design.",
        slogan="Baking Spirits Bright",
        seasonality="Winter",
        target_buyer="Bakers, crafters",
        intended_product_uses=["sublimation", "apron", "mug"],
        title="Retro Christmas Baking PNG Sublimation Graphic",
        description="4500x5400 px transparent PNG.",
        tags=["christmas baking", "gingerbread png", "sublimation design"],
        taxonomy_id=6844,
        taxonomy_path="Craft Supplies & Tools > Clip Art & Image Files",
        available_properties=sample_arbitrary_etsy_properties,
    )

    prompt = build_taxonomy_ai_prompt(context)

    assert "Retro Christmas Baking" in prompt
    assert "Baking Spirits Bright" in prompt
    assert "82731" in prompt
    assert "Sublimation" in prompt
    assert "441908" in prompt
    assert "CRITICAL RULES:" in prompt
