"""Unit tests for Phase A: Reliability & Context Integrity."""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.application.unit_of_work import UnitOfWork
from app.application.workflow_context import (
    invalidate_downstream,
    resolve_current_workflow_context,
)
from app.domain.enums import ConceptStatus, IdeaMode
from app.domain.workflow_context import (
    ArtworkContextSnapshot,
    ConceptContextSnapshot,
    ContextStatus,
    ProductionContextSnapshot,
    compute_artwork_context_hash,
    compute_concept_context_hash,
    compute_etsy_sync_hash,
    compute_listing_context_hash,
    compute_mockup_set_hash,
    compute_production_context_hash,
    compute_variant_set_hash,
)
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductConcept,
    ProductWorkflow,
)


def test_deterministic_hashes_consistency() -> None:
    """Context hashes must be deterministic, pure functions."""
    wf_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    snapshot1 = ConceptContextSnapshot(
        id=concept_id,
        version=1,
        title="Highland Cow Teacher",
        description="Cute highland cow for back to school",
        target_buyer="Teachers",
        niche="Back to school",
        seasonality="Fall",
        visual_direction="Watercolor",
        slogan="Teaching is my superpower",
        keywords=["cow", "teacher"],
        intended_product_uses=["tshirt", "mug"],
    )
    snapshot2 = ConceptContextSnapshot(
        id=concept_id,
        version=1,
        title="Highland Cow Teacher",
        description="Cute highland cow for back to school",
        target_buyer="Teachers",
        niche="Back to school",
        seasonality="Fall",
        visual_direction="Watercolor",
        slogan="Teaching is my superpower",
        keywords=["cow", "teacher"],
        intended_product_uses=["tshirt", "mug"],
    )

    c_hash1 = compute_concept_context_hash(wf_id, snapshot1)
    c_hash2 = compute_concept_context_hash(wf_id, snapshot2)
    assert c_hash1 == c_hash2
    assert len(c_hash1) == 64

    # Different slogan must yield different hash
    snapshot_diff = ConceptContextSnapshot(
        id=concept_id,
        version=1,
        title="Highland Cow Teacher",
        description="Cute highland cow for back to school",
        target_buyer="Teachers",
        niche="Back to school",
        seasonality="Fall",
        visual_direction="Watercolor",
        slogan="Different Slogan",
        keywords=["cow", "teacher"],
        intended_product_uses=["tshirt", "mug"],
    )
    c_hash_diff = compute_concept_context_hash(wf_id, snapshot_diff)
    assert c_hash1 != c_hash_diff

    # Artwork hash chained from concept hash
    art_snap = ArtworkContextSnapshot(
        asset_id=uuid.uuid4(),
        concept_id=concept_id,
        is_approved=True,
        width=1024,
        height=1024,
        dpi=300,
        has_transparent_pixels=True,
        checksum_sha256="sha256_art_123",
        visual_summary="Cow with glasses",
    )
    art_hash1 = compute_artwork_context_hash(c_hash1, art_snap)
    art_hash2 = compute_artwork_context_hash(c_hash1, art_snap)
    assert art_hash1 == art_hash2
    assert len(art_hash1) == 64
    assert art_hash1 != compute_artwork_context_hash(c_hash_diff, art_snap)


@pytest.mark.asyncio
async def test_workflow_context_resolution_and_invalidation() -> None:
    """Test full context resolution and downstream invalidation cascade with mock UOW."""
    user_id = uuid.uuid4()
    wf_id = uuid.uuid4()

    workflow = ProductWorkflow(
        id=wf_id,
        owner_id=user_id,
        name="Highland Cow Campaign",
        idea_mode=IdeaMode.MARKET_LED,
        target_marketplace="etsy",
        target_country="US",
        output_language="en",
        state="IDEA_SELECTION",
        version=1,
    )

    c1 = ProductConcept(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        title="Highland Cow Teacher",
        description="Cute cow",
        origin="market",
        differentiation="Unique art",
        status=ConceptStatus.APPROVED.value,
    )
    c2 = ProductConcept(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        title="Skeleton Reading Book",
        description="Sarcastic skeleton",
        origin="market",
        differentiation="Dark humor",
        status=ConceptStatus.PROPOSED.value,
    )

    art_asset = Asset(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        storage_key=f"workflows/{wf_id}/artwork/art1.png",
        mime_type="image/png",
        byte_size=1024 * 1024,
        checksum_sha256="art_sha_12345",
        width=1024,
        height=1024,
        has_alpha=True,
        has_transparent_pixels=True,
        provenance={
            "asset_type": "artwork",
            "concept_id": str(c1.id),
            "concept_version": 1,
            "approved": True,
        },
    )

    master_asset = Asset(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        derived_from_id=art_asset.id,
        storage_key=f"workflows/{wf_id}/production/master.png",
        mime_type="image/png",
        byte_size=15 * 1024 * 1024,
        checksum_sha256="master_sha_54321",
        width=4500,
        height=5400,
        has_alpha=True,
        has_transparent_pixels=True,
        provenance={
            "asset_type": "production_master",
            "concept_id": str(c1.id),
            "concept_version": 1,
            "artwork_asset_id": str(art_asset.id),
            "qa_passed": True,
        },
    )

    snap1 = ConceptContextSnapshot(
        id=c1.id,
        version=1,
        title=c1.title,
        description=c1.description or "",
        target_buyer=c1.target_buyer,
        niche="Digital PNG Crafters & Sublimation",
        seasonality=c1.seasonality,
        visual_direction=None,
        slogan=None,
        keywords=[],
        intended_product_uses=[],
    )
    c_hash = compute_concept_context_hash(wf_id, snap1)
    art_snap = ArtworkContextSnapshot(
        asset_id=art_asset.id,
        concept_id=c1.id,
        is_approved=True,
        width=1024,
        height=1024,
        dpi=300,
        has_transparent_pixels=True,
        checksum_sha256=art_asset.checksum_sha256,
        visual_summary=None,
    )
    a_hash = compute_artwork_context_hash(c_hash, art_snap)
    prod_snap = ProductionContextSnapshot(
        master_asset_id=master_asset.id,
        job_id=None,
        width=4500,
        height=5400,
        dpi=300,
        checksum_sha256=master_asset.checksum_sha256,
        has_transparent_background=True,
        qa_passed=True,
    )
    p_hash = compute_production_context_hash(a_hash, prod_snap)
    v_hash = compute_variant_set_hash(p_hash, [])
    l_hash = compute_listing_context_hash(p_hash, v_hash, package_file_count=1)

    listing = ListingDraft(
        id=uuid.uuid4(),
        workflow_id=wf_id,
        title="Highland Cow Teacher T-Shirt",
        description="Highland cow teacher back to school shirt",
        shopping_cart_summary="Cute cow shirt",
        tags=["highland cow", "teacher shirt"],
        concept_id=c1.id,
        artwork_asset_id=art_asset.id,
        listing_context_hash=l_hash,
        etsy_properties={"stale_reason": None},
    )

    # Set up mock UOW
    uow = MagicMock(spec=UnitOfWork)
    uow.workflows = MagicMock()
    uow.workflows.get = AsyncMock(return_value=workflow)
    uow.concepts = MagicMock()
    uow.concepts.list_for_workflow = AsyncMock(return_value=[c1, c2])
    uow.concepts.get = AsyncMock(side_effect=lambda cid: c1 if cid == c1.id else c2)
    uow.concepts.prompts = AsyncMock(return_value=[])
    uow.assets = MagicMock()
    uow.assets.list_for_workflow = AsyncMock(return_value=[art_asset, master_asset])
    uow.assets.get = AsyncMock(side_effect=lambda aid: art_asset if aid == art_asset.id else master_asset)
    uow.listing_drafts = MagicMock()
    uow.listing_drafts.get_by_workflow = AsyncMock(return_value=listing)
    uow.production_jobs = MagicMock()
    uow.production_jobs.get_latest_for_workflow = AsyncMock(return_value=None)
    uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
    uow.artwork_jobs = MagicMock()
    uow.artwork_jobs.list_for_workflow = AsyncMock(return_value=[])
    uow.approvals = MagicMock()
    uow.approvals.history = AsyncMock(return_value=[])
    uow.audit = MagicMock()
    uow.audit.record = AsyncMock()
    uow.session = MagicMock()
    uow.session.flush = AsyncMock()

    # 1. Resolve context when everything is fresh
    ctx = await resolve_current_workflow_context(wf_id, user_id, uow)
    assert ctx.concept is not None
    assert ctx.concept.id == c1.id
    assert ctx.artwork is not None
    assert ctx.artwork.asset_id == art_asset.id
    assert ctx.production is not None
    assert ctx.production.master_asset_id == master_asset.id
    assert ctx.staleness.is_any_stale is False
    assert ctx.staleness.listing_status == ContextStatus.CURRENT

    # 2. Invalidate upstream concept (e.g. user selected c2 instead)
    c1.status = ConceptStatus.SHORTLISTED.value
    c2.status = ConceptStatus.APPROVED.value
    await invalidate_downstream(wf_id, "concept", c2.id, uow)

    ctx2 = await resolve_current_workflow_context(wf_id, user_id, uow)
    assert ctx2.concept is not None
    assert ctx2.concept.id == c2.id
    # Artwork, master, and listing were based on c1, so they must be flagged STALE/SUPERSEDED
    assert ctx2.staleness.is_any_stale is True
    assert ctx2.staleness.artwork_status in (ContextStatus.SUPERSEDED, ContextStatus.STALE)
    assert ctx2.staleness.production_status in (ContextStatus.SUPERSEDED, ContextStatus.STALE)
    assert ctx2.staleness.listing_status == ContextStatus.STALE
    assert listing.listing_context_hash is None

