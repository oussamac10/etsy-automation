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
    assert res1.taxonomy_id == res2.taxonomy_id
    assert res1.taxonomy_id == 6844
    assert res1.taxonomy_path == "Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files"


@pytest.mark.asyncio
async def test_resolver_selects_sublimation_category_over_paper_craft_for_tshirt() -> None:
    """When evaluating Candidate A (paper craft) vs Candidate B (sublimation/printing),

    for a T-shirt / sublimation PNG campaign, Candidate B wins based on property fitness.
    """
    from app.ports.providers import EtsyTaxonomyProperty

    candidate_a = EtsyTaxonomyNode(
        id=111,
        level=3,
        name="Clip Art & Papercraft",
        full_path="Craft Supplies & Tools > Canvas & Surfaces > Clip Art & Papercraft",
    )
    candidate_b = EtsyTaxonomyNode(
        id=222,
        level=3,
        name="Digital Graphics & Sublimation Files",
        full_path="Art & Collectibles > Drawing & Illustration > Digital Graphics & Sublimation Files",
    )

    props_map = {
        111: [
            EtsyTaxonomyProperty(
                property_id=82731,
                name="Craft type",
                is_required=True,
                supports_attributes=True,
                is_multivalued=True,
                possible_values=[
                    {"value_id": 1, "name": "Card making & stationery"},
                    {"value_id": 2, "name": "Collage"},
                    {"value_id": 3, "name": "Scrapbooking"},
                ],
            )
        ],
        222: [
            EtsyTaxonomyProperty(
                property_id=82731,
                name="Craft type",
                is_required=True,
                supports_attributes=True,
                is_multivalued=True,
                possible_values=[
                    {"value_id": 10, "name": "Printing & printmaking"},
                    {"value_id": 11, "name": "Sublimation"},
                    {"value_id": 12, "name": "Fabric printing"},
                ],
            )
        ],
    }

    resolver = EtsyTaxonomyResolver()
    result = resolver.resolve(
        title="Retro Dog PNG Sublimation T-shirt Design",
        tags=["dog sublimation", "tshirt graphic", "transparent png"],
        product_type="digital_png",
        intended_product_uses=["t_shirt", "sweatshirt", "sublimation"],
        nodes=[candidate_a, candidate_b],
        properties_map=props_map,
    )

    assert result.taxonomy_id == 222
    assert result.taxonomy_path == candidate_b.full_path
    assert result.fit_result is not None
    assert result.fit_result.score >= 0.85
    assert result.fit_result.has_mismatched_required_attributes is False


@pytest.mark.asyncio
async def test_resolver_uses_cache_during_gateway_resolution() -> None:
    from app.ports.providers import EtsyTaxonomyProperty

    candidate = EtsyTaxonomyNode(
        id=333,
        level=2,
        name="Digital Prints & Posters",
        full_path="Art & Collectibles > Prints > Digital Prints & Posters",
    )

    fetch_count = 0

    async def mock_fetcher(tax_id: int) -> list[EtsyTaxonomyProperty]:
        nonlocal fetch_count
        fetch_count += 1
        return [
            EtsyTaxonomyProperty(
                property_id=1,
                name="Primary color",
                is_required=False,
                supports_attributes=True,
                is_multivalued=False,
                possible_values=[{"value_id": 1, "name": "Blue"}],
            )
        ]

    resolver = EtsyTaxonomyResolver()
    # First call fetches from mock_fetcher
    res1 = await resolver.resolve_with_gateway(
        title="Botanical Art Poster",
        tags=["poster", "wall art"],
        nodes=[candidate],
        property_fetcher=mock_fetcher,
    )
    assert fetch_count == 1
    assert res1.taxonomy_id == 333

    # Second call uses internal cache
    res2 = await resolver.resolve_with_gateway(
        title="Botanical Art Poster",
        tags=["poster", "wall art"],
        nodes=[candidate],
        property_fetcher=mock_fetcher,
    )
    assert fetch_count == 1
    assert res2.taxonomy_id == 333


def test_case_3_best_available_fallback_when_no_sublimation_properties_exist() -> None:
    """When all candidate digital categories only have paper-oriented craft types,

    resolver returns the best legitimate digital category, marks best_available = True,
    includes a warning, and does NOT invent fake values.
    """
    from app.ports.providers import EtsyTaxonomyProperty

    candidate_a = EtsyTaxonomyNode(
        id=6844,
        level=3,
        name="Clip Art & Image Files",
        full_path="Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files",
    )

    props_map = {
        6844: [
            EtsyTaxonomyProperty(
                property_id=82731,
                name="Craft type",
                is_required=True,
                supports_attributes=True,
                is_multivalued=True,
                possible_values=[
                    {"value_id": 1, "name": "Card making & stationery"},
                    {"value_id": 2, "name": "Collage"},
                    {"value_id": 3, "name": "Kids' crafts"},
                    {"value_id": 4, "name": "Scrapbooking"},
                ],
            )
        ]
    }

    resolver = EtsyTaxonomyResolver()
    result = resolver.resolve(
        title="Retro Camping Dog PNG Sublimation Design",
        tags=["sublimation", "tshirt png", "pod graphics"],
        product_type="digital_png",
        intended_product_uses=["t_shirt", "sweatshirt", "sublimation"],
        nodes=[candidate_a],
        properties_map=props_map,
    )

    assert result.taxonomy_id == 6844
    assert result.fit_result is not None
    assert result.fit_result.best_available is True
    assert result.fit_result.has_mismatched_required_attributes is True
    assert any("precisely matches" in w for w in result.fit_result.warnings)

