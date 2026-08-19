"""Tests for Etsy Seller Taxonomy Resolution."""

import pytest
from app.domain.taxonomy_resolver import EtsyTaxonomyResolver
from app.ports.providers import EtsyTaxonomyNode
from app.providers.fake import FakeEtsyProvider


@pytest.fixture
def fake_taxonomy_nodes() -> list[EtsyTaxonomyNode]:
    fake_gateway = FakeEtsyProvider()
    import asyncio
    return asyncio.run(fake_gateway.get_seller_taxonomy_nodes())


def test_resolver_resolves_transparent_png_to_clip_art(fake_taxonomy_nodes: list[EtsyTaxonomyNode]) -> None:
    resolver = EtsyTaxonomyResolver()
    result = resolver.resolve(
        title="Cute Retro Cat PNG Graphic Sublimation Design",
        tags=["cat png", "sublimation cat", "clipart", "retro cat", "png download"],
        product_type="digital_png",
        nodes=fake_taxonomy_nodes,
    )
    assert result.taxonomy_id == 6844
    assert "Clip Art & Image Files" in result.taxonomy_path
    assert "Craft Supplies & Tools" in result.taxonomy_path
    assert result.confidence >= 0.8


def test_resolver_resolves_printable_wall_art_to_digital_prints(fake_taxonomy_nodes: list[EtsyTaxonomyNode]) -> None:
    resolver = EtsyTaxonomyResolver()
    result = resolver.resolve(
        title="Minimalist Botanical Wall Art Printable Poster",
        tags=["printable wall art", "poster print", "modern decor", "botanical print"],
        product_type="digital_print",
        nodes=fake_taxonomy_nodes,
    )
    assert result.taxonomy_id == 2078
    assert "Prints > Digital Prints" in result.taxonomy_path
    assert result.confidence >= 0.8


def test_resolver_resolves_digital_illustration(fake_taxonomy_nodes: list[EtsyTaxonomyNode]) -> None:
    resolver = EtsyTaxonomyResolver()
    result = resolver.resolve(
        title="Hand Drawn Line Art Portrait Digital Illustration",
        tags=["line art", "digital drawing", "portrait sketch", "illustration"],
        product_type="digital_drawing",
        nodes=fake_taxonomy_nodes,
    )
    assert result.taxonomy_id == 77
    assert "Drawing & Illustration > Digital" in result.taxonomy_path


def test_resolver_strictly_rejects_physical_categories(fake_taxonomy_nodes: list[EtsyTaxonomyNode]) -> None:
    resolver = EtsyTaxonomyResolver()
    # Even if title mentions "t-shirt graphic" or "mug sublimation"
    result = resolver.resolve(
        title="Vintage Sunset T-Shirt Graphic For Sublimation Mug Plate",
        tags=["t-shirt design", "mug design", "sublimation png", "retro sunset"],
        nodes=fake_taxonomy_nodes,
    )
    # Must NOT select physical plates (1049) or physical clothing
    assert result.taxonomy_id != 1049
    assert not resolver.is_physical_disqualified(result.taxonomy_path)
    assert "Plates" not in result.taxonomy_path
    assert "Kitchen & Dining" not in result.taxonomy_path
    assert result.taxonomy_id == 6844  # Clip Art & Image Files


def test_resolver_deterministic_without_nodes() -> None:
    resolver = EtsyTaxonomyResolver()
    res1 = resolver.resolve(
        title="Vintage Sunset T-Shirt Graphic",
        tags=["sublimation png", "clipart"],
    )
    res2 = resolver.resolve(
        title="Vintage Sunset T-Shirt Graphic",
        tags=["sublimation png", "clipart"],
    )
    assert res1 == res2
    assert res1.taxonomy_id == 6844
    assert res1.taxonomy_path == "Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files"
