"""Tests for Phase 9 deterministic SKU generation."""

import uuid
from app.domain.sku_generator import (
    derive_shop_prefix,
    extract_sku_keywords,
    generate_sku,
)


class TestSkuGenerator:
    def test_derive_shop_prefix(self):
        assert derive_shop_prefix("NovaCraftPixel") == "NOVA"
        assert derive_shop_prefix("Digital Art Studio") == "DAS"
        assert derive_shop_prefix("Vintage") == "VINT"
        assert derive_shop_prefix("") == "ET"
        assert derive_shop_prefix(None) == "ET"

    def test_extract_sku_keywords(self):
        assert extract_sku_keywords("Retro Christmas Baking PNG Sublimation") in ("RETRO-CHRIS", "RETRO-BAKIN")
        assert extract_sku_keywords("Pumpkin Spice Clipart") in ("PUMPK-SPICE", "PUMPK")

    def test_generate_sku_stability(self):
        workflow_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
        sku1 = generate_sku(
            shop_name="NovaCraftPixel",
            title_or_concept="Retro Christmas Baking PNG Sublimation Clipart",
            workflow_id=workflow_id,
        )
        sku2 = generate_sku(
            shop_name="NovaCraftPixel",
            title_or_concept="Retro Christmas Baking PNG Sublimation Clipart",
            workflow_id=workflow_id,
        )
        # Deterministic stability
        assert sku1 == sku2
        assert sku1.startswith("NOVA-")
        assert len(sku1) <= 32

    def test_generate_sku_different_workflow_ids_differ(self):
        wf1 = uuid.UUID("11111111-2222-3333-4444-555555555555")
        wf2 = uuid.UUID("99999999-8888-7777-6666-555555555555")
        sku1 = generate_sku("Shop A", "Art Title", wf1)
        sku2 = generate_sku("Shop A", "Art Title", wf2)
        assert sku1 != sku2
