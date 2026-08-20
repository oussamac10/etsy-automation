"""Tests for Phase 9 Etsy payload builder and strict draft compliance."""

import pytest
from app.domain.errors import DomainError
from app.domain.etsy_payload_builder import build_etsy_listing_payload


class TestEtsyPayloadBuilder:
    def test_build_etsy_listing_payload_draft_guarantee(self):
        payload = build_etsy_listing_payload(
            title="Retro Christmas Baking PNG Sublimation Clipart",
            description="High quality PNG sublimation graphic for holiday crafting.",
            tags=[
                "retro baking",
                "christmas cookies",
                "sublimation png",
                "holiday clipart",
                "baking design",
                "vintage kitchen",
                "gingerbread man",
                "festive craft",
                "cookie cutter",
                "sweet treats",
                "winter graphics",
                "seasonal print",
                "digital download",
            ],
            price_minor_units=499,
            currency="USD",
            taxonomy_id=6844,
            quantity=999,
            shop_section_id="12345",
            should_auto_renew=True,
        )

        # Strict safety requirements: Draft only, never active
        assert payload["state"] == "draft"
        assert payload["title"] == "Retro Christmas Baking PNG Sublimation Clipart"
        assert payload["price"] == 4.99
        assert payload["taxonomy_id"] == "6844"
        assert payload["type"] == "download"
        assert payload["who_made"] == "i_did"
        assert payload["is_supply"] == "false"
        assert payload["quantity"] == 999
        assert payload["shop_section_id"] == 12345
        assert payload["should_auto_renew"] == "true"

    def test_build_payload_missing_taxonomy_raises(self):
        with pytest.raises(DomainError, match="A valid Etsy seller taxonomy category ID is required"):
            build_etsy_listing_payload(
                title="Valid Title For Digital Art",
                description="Valid Description",
                tags=[
                    "tag one",
                    "tag two",
                    "tag three",
                    "tag four",
                    "tag five",
                    "tag six",
                    "tag seven",
                    "tag eight",
                    "tag nine",
                    "tag ten",
                    "tag eleven",
                    "tag twelve",
                    "tag thirteen",
                ],
                price_minor_units=499,
                currency="USD",
                taxonomy_id=0,  # Invalid
            )
