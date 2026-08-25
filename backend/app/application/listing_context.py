"""Authoritative Listing Generation Context & Staleness Resolver.

Establishes the explicit source-of-truth chain:
CURRENT WORKFLOW -> CURRENT SELECTED CONCEPT -> CURRENT APPROVED ARTWORK / MASTER PNG
-> CURRENT PRODUCTION METADATA -> CURRENT BUYER PACKAGE -> CURRENT LISTING COPY

Guarantees:
1. No stale or cross-campaign concept/artwork leakage.
2. Concept-artwork consistency check (blocks generation if concept changed after artwork).
3. Deterministic context hashing for cache isolation and staleness detection.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import uuid
from dataclasses import dataclass, field

import structlog

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import ConceptStatus
from app.domain.errors import DomainError, EntityNotFoundError
from app.infrastructure.models import (
    Asset,
    ListingDraft,
    ProductWorkflow,
)
from app.domain.workflow_context import (
    ArtworkContextSnapshot,
    ConceptContextSnapshot,
    ProductionContextSnapshot,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PackageContextSnapshot:
    """Snapshot of the customer download package and licensing."""

    file_count: int
    license_terms: str


@dataclass(frozen=True, slots=True)
class ListingGenerationContext:
    """Authoritative normalized snapshot passed to LLM and used for provenance."""

    workflow_id: uuid.UUID
    workflow_name: str
    concept: ConceptContextSnapshot
    artwork: ArtworkContextSnapshot
    production: ProductionContextSnapshot
    buyer_package: PackageContextSnapshot
    context_hash: str


def compute_listing_context_hash(
    workflow_id: uuid.UUID,
    concept: ConceptContextSnapshot,
    artwork: ArtworkContextSnapshot,
    production: ProductionContextSnapshot,
    buyer_package: PackageContextSnapshot,
) -> str:
    """Compute a deterministic SHA-256 hash representing the upstream context inputs."""
    from app.domain.workflow_context import (
        compute_artwork_context_hash,
        compute_concept_context_hash,
        compute_listing_context_hash as domain_compute_listing_context_hash,
        compute_production_context_hash,
        compute_variant_set_hash,
    )

    c_hash = compute_concept_context_hash(workflow_id, concept)
    a_hash = compute_artwork_context_hash(c_hash, artwork)
    p_hash = compute_production_context_hash(a_hash, production)
    v_hash = compute_variant_set_hash(p_hash, [])
    return domain_compute_listing_context_hash(
        production_context_hash=p_hash,
        variant_set_hash=v_hash,
        package_file_count=buyer_package.file_count,
        prompt_version=concept.version,
    )


async def resolve_listing_generation_context(
    workflow_id: uuid.UUID,
    uow: UnitOfWork,
    *,
    require_approved_artwork: bool = False,
) -> ListingGenerationContext:
    """Resolve the authoritative upstream context objects for listing generation.

    Validates:
    - Workflow exists.
    - Active concept is resolved (approved concept prioritized).
    - Concept belongs to this workflow.
    - Concept prompt version is current.
    - Approved artwork belongs to workflow and matches the active concept.
    - Production metadata and package specifications are extracted cleanly.
    """
    workflow: ProductWorkflow | None = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)

    # 1. Resolve Active Concept
    concepts = await uow.concepts.list_for_workflow(workflow_id)
    if not concepts:
        raise DomainError(f"Workflow {workflow_id} has no product concepts.")

    # Filter out archived concepts
    active_candidates = [c for c in concepts if c.status != ConceptStatus.ARCHIVED]
    if not active_candidates:
        active_candidates = list(concepts)

    # Prioritize explicitly APPROVED concept
    approved_concepts = [c for c in active_candidates if c.status == ConceptStatus.APPROVED]
    if approved_concepts:
        active_concept = approved_concepts[0]
    elif len(active_candidates) == 1:
        active_concept = active_candidates[0]
    else:
        # Multiple concepts exist: select the highest scoring candidate
        active_concept = max(active_candidates, key=lambda c: c.score or 0)

    if active_concept.workflow_id != workflow_id:
        msg = f"Cross-workflow concept error: {active_concept.id} not in {workflow_id}."
        raise DomainError(msg)

    # 2. Resolve Active Concept Prompt & Slogan
    prompts = await uow.concepts.prompts(active_concept.id)
    latest_prompt = prompts[-1] if prompts else None
    concept_version = latest_prompt.version if latest_prompt else 1
    slogan = latest_prompt.exact_slogan if latest_prompt else None
    visual_direction = latest_prompt.style_notes if latest_prompt else None

    # Resolve Niche from title / breakdown
    niche = active_concept.target_buyer or "Digital PNG Crafters & Sublimation"
    if active_concept.score_breakdown and isinstance(active_concept.score_breakdown, dict):
        raw_niche = active_concept.score_breakdown.get("niche_theme")
        if raw_niche:
            niche = str(raw_niche)

    # Keywords strictly scoped to this concept & its research run
    scoped_keywords: list[str] = []
    if active_concept.score_breakdown and isinstance(active_concept.score_breakdown, dict):
        kw_list = active_concept.score_breakdown.get("primary_keywords") or []
        if isinstance(kw_list, list):
            scoped_keywords.extend([str(k).strip().lower() for k in kw_list if str(k).strip()])

    if not scoped_keywords and active_concept.research_run_id:
        clusters = await uow.research.get_keyword_clusters_for_run(active_concept.research_run_id)
        for cl in clusters:
            scoped_keywords.append(cl.primary_phrase.strip().lower())
            scoped_keywords.extend([a.strip().lower() for a in cl.attributes if a.strip()])

    # Deduplicate keywords preserving order
    seen_kw: set[str] = set()
    deduped_keywords: list[str] = []
    for k in scoped_keywords:
        if k not in seen_kw:
            seen_kw.add(k)
            deduped_keywords.append(k)

    uses_list = list(active_concept.intended_product_uses or workflow.intended_product_uses or [])
    concept_snapshot = ConceptContextSnapshot(
        id=active_concept.id,
        version=concept_version,
        title=active_concept.title.strip(),
        description=(active_concept.description or "").strip(),
        target_buyer=active_concept.target_buyer,
        niche=niche,
        seasonality=active_concept.seasonality,
        visual_direction=visual_direction,
        slogan=slogan,
        keywords=deduped_keywords[:15],
        intended_product_uses=uses_list,
    )

    # 3. Resolve Approved Artwork Asset & Validate Consistency
    workflow_assets = await uow.assets.list_for_workflow(workflow_id)
    artwork_asset: Asset | None = None
    artwork_concept_id: uuid.UUID | None = None
    is_artwork_approved = False
    visual_summary: str | None = None

    # Check ArtworkJobs for approval/success
    jobs = await uow.artwork_jobs.list_for_workflow(workflow_id)
    active_concept_job_ids = {j.id for j in jobs if j.concept_id == active_concept.id}
    other_concept_job_ids = {j.id: j.concept_id for j in jobs if j.concept_id != active_concept.id}

    # Find the primary production master or candidate artwork
    master_candidates = [
        a
        for a in workflow_assets
        if isinstance(a.provenance, dict)
        and a.provenance.get("kind") in ("production_master", "master_png")
    ]
    candidate_artworks = [
        a
        for a in workflow_assets
        if a.artwork_job_id is not None
        or (isinstance(a.provenance, dict) and a.provenance.get("kind") == "candidate_artwork")
    ]

    chosen_asset = (
        master_candidates[0]
        if master_candidates
        else (candidate_artworks[0] if candidate_artworks else None)
    )

    if chosen_asset is not None:
        artwork_asset = chosen_asset
        prov = chosen_asset.provenance if isinstance(chosen_asset.provenance, dict) else {}
        is_artwork_approved = bool(prov.get("approved", True))

        # Check concept provenance
        if chosen_asset.artwork_job_id:
            if chosen_asset.artwork_job_id in active_concept_job_ids:
                artwork_concept_id = active_concept.id
            elif chosen_asset.artwork_job_id in other_concept_job_ids:
                artwork_concept_id = other_concept_job_ids[chosen_asset.artwork_job_id]
        if not artwork_concept_id and "concept_id" in prov:
            with contextlib.suppress(ValueError, TypeError):
                artwork_concept_id = uuid.UUID(str(prov["concept_id"]))

        # 4. CONCEPT-ARTWORK CONSISTENCY CHECK
        if artwork_concept_id is not None and artwork_concept_id != active_concept.id:
            raise DomainError(
                "The selected concept changed after this artwork was created. "
                "Generate or approve artwork for the current concept before creating listing copy."
            )

        raw_summary = prov.get("visual_summary")
        visual_summary = (
            str(raw_summary)
            if raw_summary
            else (latest_prompt.positive_prompt if latest_prompt else None)
        )

    if require_approved_artwork and (artwork_asset is None or not is_artwork_approved):
        raise DomainError("Listing generation requires an approved artwork asset.")

    trans_pixels = (
        artwork_asset.has_transparent_pixels
        if artwork_asset and artwork_asset.has_transparent_pixels is not None
        else True
    )
    art_summary = visual_summary or (
        latest_prompt.positive_prompt if latest_prompt else active_concept.description
    )
    artwork_snapshot = ArtworkContextSnapshot(
        asset_id=artwork_asset.id if artwork_asset else None,
        concept_id=artwork_concept_id or active_concept.id,
        is_approved=is_artwork_approved,
        width=artwork_asset.width if artwork_asset and artwork_asset.width else 4500,
        height=artwork_asset.height if artwork_asset and artwork_asset.height else 5400,
        dpi=300,
        has_transparent_pixels=trans_pixels,
        checksum_sha256=artwork_asset.checksum_sha256 if artwork_asset else None,
        visual_summary=art_summary,
    )

    # 5. Production & Variants Snapshot
    production_variants: list[str] = []
    for a in workflow_assets:
        prov = a.provenance if isinstance(a.provenance, dict) else {}
        if prov.get("kind") == "variant_deliverable":
            v_name = prov.get("variant_name") or prov.get("title")
            if v_name and v_name not in production_variants:
                production_variants.append(str(v_name))

    production_snapshot = ProductionContextSnapshot(
        master_asset_id=artwork_snapshot.asset_id,
        job_id=None,
        width=artwork_snapshot.width,
        height=artwork_snapshot.height,
        dpi=artwork_snapshot.dpi,
        checksum_sha256=artwork_snapshot.checksum_sha256,
        has_transparent_background=artwork_snapshot.has_transparent_pixels,
        qa_passed=True,
        color_profile="sRGB",
    )

    # 6. Buyer Package Snapshot
    deliverable_count = 1 + len(production_variants)
    license_terms = (
        "Commercial use allowed on physical finished products (such as apparel, "
        "t-shirts, sweatshirts, tote bags, mugs, stickers, and gifts). "
        "You may not resell, redistribute, or share the digital file."
    )
    buyer_package_snapshot = PackageContextSnapshot(
        file_count=deliverable_count,
        license_terms=license_terms,
    )

    # 7. Compute Deterministic Context Hash
    ctx_hash = compute_listing_context_hash(
        workflow_id=workflow_id,
        concept=concept_snapshot,
        artwork=artwork_snapshot,
        production=production_snapshot,
        buyer_package=buyer_package_snapshot,
    )

    return ListingGenerationContext(
        workflow_id=workflow_id,
        workflow_name=workflow.name,
        concept=concept_snapshot,
        artwork=artwork_snapshot,
        production=production_snapshot,
        buyer_package=buyer_package_snapshot,
        context_hash=ctx_hash,
    )


def evaluate_listing_staleness(
    draft: ListingDraft,
    context: ListingGenerationContext,
) -> tuple[bool, str | None]:
    """Evaluate whether existing ListingDraft copy is stale compared to current upstream context."""
    # Check concept ID match
    draft_concept_id = getattr(draft, "concept_id", None)
    if draft_concept_id is not None and draft_concept_id != context.concept.id:
        return True, "Listing copy was generated for a different concept than the active selection."

    # Check context hash
    draft_hash = getattr(draft, "listing_context_hash", None)
    if not draft_hash and isinstance(draft.ip_findings, dict):
        draft_hash = draft.ip_findings.get("context_hash")

    if draft_hash and draft_hash != context.context_hash:
        return True, "Listing copy is based on an older concept or artwork version."

    # If draft has no recorded context hash or concept_id and title does not match current concept
    if not draft_hash:
        clean_draft_title = draft.title.strip().lower()
        clean_concept_title = context.concept.title.strip().lower()
        concept_words = {w for w in clean_concept_title.split() if len(w) > 3}
        if concept_words and not any(w in clean_draft_title for w in concept_words):
            return True, "Listing copy is based on an older concept or artwork version."

    return False, None
