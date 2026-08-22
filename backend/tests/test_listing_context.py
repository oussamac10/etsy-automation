"""Unit tests for listing generation context resolver, context hashing, and staleness evaluator."""

from __future__ import annotations

import uuid

from app.application.listing_context import (
    ArtworkContextSnapshot,
    ConceptContextSnapshot,
    ListingGenerationContext,
    PackageContextSnapshot,
    ProductionContextSnapshot,
    compute_listing_context_hash,
    evaluate_listing_staleness,
)
from app.infrastructure.models import ListingDraft

ContextSnapshotsTuple = tuple[
    uuid.UUID,
    ConceptContextSnapshot,
    ArtworkContextSnapshot,
    ProductionContextSnapshot,
    PackageContextSnapshot,
]


def _make_context_snapshots(
    workflow_id: uuid.UUID | None = None,
    concept_id: uuid.UUID | None = None,
    title: str = "Highland Cow Teacher Back to School Calf",
    version: int = 1,
) -> ContextSnapshotsTuple:
    wf_id = workflow_id or uuid.uuid4()
    c_id = concept_id or uuid.uuid4()
    art_id = uuid.uuid4()

    concept = ConceptContextSnapshot(
        id=c_id,
        version=version,
        title=title,
        description="Cute highland cow calf wearing teacher glasses with pencils",
        target_buyer="Teachers & Crafters",
        niche="Teacher Apparel",
        seasonality="Back to School",
        visual_direction="Kawaii cute watercolor illustration",
        slogan=None,
        keywords=["teacher highland cow png", "back to school clipart"],
        intended_product_uses=["T-Shirt", "Mug", "Tote"],
    )
    artwork = ArtworkContextSnapshot(
        asset_id=art_id,
        concept_id=c_id,
        is_approved=True,
        width=4500,
        height=5400,
        dpi=300,
        has_transparent_pixels=True,
        checksum_sha256="abc123sha",
        visual_summary="Highland cow calf with teacher glasses",
    )
    production = ProductionContextSnapshot(
        width=4500,
        height=5400,
        dpi=300,
        has_transparent_background=True,
        variants=["Dark garment PNG", "Light garment PNG"],
        color_profile="sRGB",
    )
    buyer_package = PackageContextSnapshot(
        file_count=3,
        license_terms="Commercial physical products use allowed.",
    )
    return wf_id, concept, artwork, production, buyer_package


def test_compute_listing_context_hash_deterministic():
    wf_id, concept, artwork, production, buyer_package = _make_context_snapshots()
    hash1 = compute_listing_context_hash(wf_id, concept, artwork, production, buyer_package)
    hash2 = compute_listing_context_hash(wf_id, concept, artwork, production, buyer_package)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_compute_listing_context_hash_changes_on_input_delta():
    wf_id, concept, artwork, production, buyer_package = _make_context_snapshots()
    base_hash = compute_listing_context_hash(wf_id, concept, artwork, production, buyer_package)

    # Change concept title
    concept_delta = ConceptContextSnapshot(
        id=concept.id,
        version=concept.version,
        title="Different Concept Title",
        description=concept.description,
        target_buyer=concept.target_buyer,
        niche=concept.niche,
        seasonality=concept.seasonality,
        visual_direction=concept.visual_direction,
        slogan=concept.slogan,
    )
    delta_hash = compute_listing_context_hash(
        wf_id, concept_delta, artwork, production, buyer_package
    )
    assert delta_hash != base_hash

    # Change artwork checksum
    artwork_delta = ArtworkContextSnapshot(
        asset_id=artwork.asset_id,
        concept_id=artwork.concept_id,
        is_approved=artwork.is_approved,
        width=artwork.width,
        height=artwork.height,
        dpi=artwork.dpi,
        has_transparent_pixels=artwork.has_transparent_pixels,
        checksum_sha256="different_sha",
        visual_summary=artwork.visual_summary,
    )
    artwork_hash = compute_listing_context_hash(
        wf_id, concept, artwork_delta, production, buyer_package
    )
    assert artwork_hash != base_hash


def test_evaluate_listing_staleness_matching():
    wf_id, concept, artwork, production, buyer_package = _make_context_snapshots()
    ctx_hash = compute_listing_context_hash(wf_id, concept, artwork, production, buyer_package)

    ctx = ListingGenerationContext(
        workflow_id=wf_id,
        workflow_name="Highland Cow Teacher",
        concept=concept,
        artwork=artwork,
        production=production,
        buyer_package=buyer_package,
        context_hash=ctx_hash,
    )

    draft = ListingDraft(
        workflow_id=wf_id,
        concept_id=concept.id,
        concept_version=concept.version,
        artwork_asset_id=artwork.asset_id,
        listing_context_hash=ctx_hash,
        title="Highland Cow Teacher PNG, Back to School Sublimation Design",
        description="Cute illustration description",
        tags=["teacher png", "cow clipart"],
        ip_findings={"context_hash": ctx_hash},
    )

    is_stale, reason = evaluate_listing_staleness(draft, ctx)
    assert not is_stale
    assert reason is None


def test_evaluate_listing_staleness_mismatched_concept():
    wf_id, concept, artwork, production, buyer_package = _make_context_snapshots()
    ctx_hash = compute_listing_context_hash(wf_id, concept, artwork, production, buyer_package)

    ctx = ListingGenerationContext(
        workflow_id=wf_id,
        workflow_name="Highland Cow Teacher",
        concept=concept,
        artwork=artwork,
        production=production,
        buyer_package=buyer_package,
        context_hash=ctx_hash,
    )

    # Draft was generated for a different concept ID
    other_concept_id = uuid.uuid4()
    draft = ListingDraft(
        workflow_id=wf_id,
        concept_id=other_concept_id,
        concept_version=1,
        artwork_asset_id=artwork.asset_id,
        listing_context_hash="stale_hash_value",
        title="Sarcastic Bookworm Skeleton PNG",
        description="Skeleton illustration",
        tags=["skeleton png", "bookworm"],
        ip_findings={"context_hash": "stale_hash_value"},
    )

    is_stale, reason = evaluate_listing_staleness(draft, ctx)
    assert is_stale
    assert "different concept" in reason.lower() or "older concept" in reason.lower()
