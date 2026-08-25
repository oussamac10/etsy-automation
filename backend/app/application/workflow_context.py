"""Authoritative Application Service for Workflow Context Resolution and Invalidation.

Single source of truth for:
1. Resolving the current valid upstream-to-downstream context graph.
2. Checking provenance integrity and computing deterministic context hashes.
3. Marking downstream artifacts as STALE/SUPERSEDED upon upstream changes.
"""

from __future__ import annotations

import contextlib
import inspect
import uuid
from typing import Any

import structlog

from app.application.unit_of_work import UnitOfWork
from app.domain.artwork_variants import (
    VariantStatus,
    filter_workflow_artwork_variants,
    is_valid_artwork_variant_asset,
    is_variant_outdated,
)
from app.domain.enums import AuditAction, ConceptStatus
from app.domain.errors import DomainError, EntityNotFoundError
from app.domain.production_resolver import (
    filter_active_user_mockups,
)
from app.domain.workflow import ApprovalDecision, ApprovalGate
from app.domain.workflow_context import (
    ArtworkContextSnapshot,
    ConceptContextSnapshot,
    ContextHashes,
    ContextStatus,
    EtsyDraftContextSnapshot,
    MockupContextSnapshot,
    PackageContextSnapshot,
    ProductionContextSnapshot,
    StalenessReport,
    VariantContextSnapshot,
    WorkflowContextSnapshot,
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
    ProductWorkflow,
)

logger = structlog.get_logger(__name__)


async def _maybe_await(obj: Any) -> Any:
    if inspect.isawaitable(obj):
        return await obj
    return obj


async def resolve_current_workflow_context(
    workflow_id: uuid.UUID,
    owner_id: uuid.UUID,
    uow: UnitOfWork,
) -> WorkflowContextSnapshot:
    """Authoritatively resolve the full provenance graph and staleness report for a workflow."""
    workflow: ProductWorkflow | None = await uow.workflows.get(workflow_id)
    if workflow is None:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)
    if workflow.owner_id != owner_id:
        raise DomainError(f"Workflow {workflow_id} does not belong to owner {owner_id}.")

    # 1. Resolve Active Concept
    concepts = await _maybe_await(uow.concepts.list_for_workflow(workflow_id))
    active_concept = None
    if concepts:
        approved_concepts = [c for c in concepts if c.status == ConceptStatus.APPROVED]
        if approved_concepts:
            active_concept = approved_concepts[0]
        else:
            active_candidates = [c for c in concepts if c.status != ConceptStatus.ARCHIVED]
            if active_candidates:
                active_concept = (
                    active_candidates[0]
                    if len(active_candidates) == 1
                    else max(active_candidates, key=lambda c: c.score or 0)
                )

    concept_snapshot: ConceptContextSnapshot | None = None
    if active_concept is not None:
        prompts = await _maybe_await(uow.concepts.prompts(active_concept.id)) if hasattr(uow.concepts, "prompts") else []
        latest_prompt = prompts[-1] if prompts else None
        concept_version = latest_prompt.version if latest_prompt else 1
        slogan = latest_prompt.exact_slogan if latest_prompt else None
        visual_direction = latest_prompt.style_notes if latest_prompt else None

        niche = active_concept.target_buyer or "Digital PNG Crafters & Sublimation"
        if active_concept.score_breakdown and isinstance(active_concept.score_breakdown, dict):
            raw_niche = active_concept.score_breakdown.get("niche_theme")
            if raw_niche:
                niche = str(raw_niche)

        scoped_keywords: list[str] = []
        if active_concept.score_breakdown and isinstance(active_concept.score_breakdown, dict):
            kw_list = active_concept.score_breakdown.get("primary_keywords") or []
            if isinstance(kw_list, list):
                scoped_keywords.extend(
                    [str(k).strip().lower() for k in kw_list if str(k).strip()]
                )

        if not scoped_keywords and active_concept.research_run_id and hasattr(uow, "research") and hasattr(uow.research, "get_keyword_clusters_for_run"):
            clusters = await _maybe_await(uow.research.get_keyword_clusters_for_run(
                active_concept.research_run_id
            ))
            for cl in (clusters or []):
                scoped_keywords.append(cl.primary_phrase.strip().lower())
                scoped_keywords.extend([a.strip().lower() for a in cl.attributes if a.strip()])

        seen_kw: set[str] = set()
        deduped_keywords: list[str] = []
        for k in scoped_keywords:
            if k not in seen_kw:
                seen_kw.add(k)
                deduped_keywords.append(k)

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
            intended_product_uses=list(
                active_concept.intended_product_uses or workflow.intended_product_uses or []
            ),
        )

    # 2. Resolve Approved Artwork Asset
    workflow_assets = await _maybe_await(uow.assets.list_for_workflow(workflow_id))
    approvals = await _maybe_await(uow.approvals.history(workflow_id, gate=ApprovalGate.ARTWORK_APPROVAL)) if hasattr(uow, "approvals") and hasattr(uow.approvals, "history") else []
    approved_gate2 = next((a for a in (approvals or []) if a.decision == ApprovalDecision.APPROVED), None)

    approved_artwork_asset: Asset | None = None
    if approved_gate2 and approved_gate2.target_id:
        target = await _maybe_await(uow.assets.get(approved_gate2.target_id))
        if target and target.workflow_id == workflow_id:
            approved_artwork_asset = target

    # Fallback to asset explicitly marked as approved or production master source
    if approved_artwork_asset is None:
        for a in (workflow_assets or []):
            if isinstance(a.provenance, dict) and a.provenance.get("approved"):
                approved_artwork_asset = a
                break

    artwork_snapshot: ArtworkContextSnapshot | None = None
    artwork_concept_id: uuid.UUID | None = None
    if approved_artwork_asset is not None:
        prov = (
            approved_artwork_asset.provenance
            if isinstance(approved_artwork_asset.provenance, dict)
            else {}
        )
        if approved_artwork_asset.artwork_job_id and hasattr(uow, "artwork_jobs") and hasattr(uow.artwork_jobs, "get"):
            job = await _maybe_await(uow.artwork_jobs.get(approved_artwork_asset.artwork_job_id))
            if job:
                artwork_concept_id = job.concept_id
        if not artwork_concept_id and "concept_id" in prov:
            with contextlib.suppress(ValueError, TypeError):
                artwork_concept_id = uuid.UUID(str(prov["concept_id"]))

        artwork_snapshot = ArtworkContextSnapshot(
            asset_id=approved_artwork_asset.id,
            concept_id=artwork_concept_id or (active_concept.id if active_concept else None),
            is_approved=True,
            width=approved_artwork_asset.width or 0,
            height=approved_artwork_asset.height or 0,
            dpi=300,
            has_transparent_pixels=bool(approved_artwork_asset.has_transparent_pixels),
            checksum_sha256=approved_artwork_asset.checksum_sha256,
            visual_summary=str(prov.get("visual_summary"))
            if prov.get("visual_summary")
            else None,
        )

    # 3. Resolve Production Master PNG
    master_asset: Asset | None = None
    production_jobs = (
        await _maybe_await(uow.production_jobs.list_for_workflow(workflow_id))
        if hasattr(uow, "production_jobs") and hasattr(uow.production_jobs, "list_for_workflow")
        else []
    )
    latest_prod_job = production_jobs[0] if production_jobs else None

    if latest_prod_job and latest_prod_job.output_asset_id:
        out_asset = await _maybe_await(uow.assets.get(latest_prod_job.output_asset_id))
        if out_asset and out_asset.workflow_id == workflow_id:
            master_asset = out_asset

    if master_asset is None:
        for a in workflow_assets:
            if (
                a.storage_key.endswith("/master.png")
                or (
                    isinstance(a.provenance, dict)
                    and a.provenance.get("profile") == "etsy-png-standard"
                )
            ) and "/mockups/" not in a.storage_key:
                master_asset = a
                break

    if master_asset is None and approved_artwork_asset is not None:
        master_asset = approved_artwork_asset

    production_snapshot: ProductionContextSnapshot | None = None
    if master_asset is not None:
        production_snapshot = ProductionContextSnapshot(
            master_asset_id=master_asset.id,
            job_id=latest_prod_job.id if latest_prod_job else None,
            width=master_asset.width or 4000,
            height=master_asset.height or 4000,
            dpi=300,
            checksum_sha256=master_asset.checksum_sha256,
            has_transparent_background=bool(master_asset.has_transparent_pixels),
            qa_passed=latest_prod_job.qa_passed if latest_prod_job else True,
        )

    # 4. Resolve Artwork Color Variants
    raw_variants = filter_workflow_artwork_variants(list(workflow_assets))
    active_variant_ids: list[uuid.UUID] = []
    included_in_package_ids: list[uuid.UUID] = []
    included_checksums: list[str] = []

    for v in raw_variants:
        prov = v.provenance or {}
        if prov.get("variant_status") == VariantStatus.APPROVED.value:
            active_variant_ids.append(v.id)
            if prov.get("include_in_buyer_package"):
                is_stale_var = master_asset and is_variant_outdated(v, master_asset)
                if not is_stale_var:
                    included_in_package_ids.append(v.id)
                    included_checksums.append(v.checksum_sha256)

    # 5. Resolve Active User Mockups
    active_mockups = filter_active_user_mockups(
        workflow_assets,
        master_asset_id=master_asset.id if master_asset else None,
    )
    mockup_ids = [m.id for m in active_mockups]
    template_ids = [
        str((m.provenance or {}).get("template_id", ""))
        for m in active_mockups
        if (m.provenance or {}).get("template_id")
    ]
    cover_mockup = next((m for m in active_mockups if (m.provenance or {}).get("is_cover")), None)
    cover_id = cover_mockup.id if cover_mockup else (mockup_ids[0] if mockup_ids else None)

    # 6. Resolve Buyer Package
    package_asset = next(
        (
            a
            for a in workflow_assets
            if a.storage_key.endswith(".zip")
            or (
                isinstance(a.provenance, dict)
                and a.provenance.get("asset_type") == "buyer_package"
            )
        ),
        None,
    )
    package_snapshot: PackageContextSnapshot | None = None
    if package_asset is not None:
        p_prov = (
            package_asset.provenance if isinstance(package_asset.provenance, dict) else {}
        )
        raw_files = p_prov.get("included_filenames", [])
        files_list = [str(f) for f in raw_files] if isinstance(raw_files, list) else []
        raw_count = p_prov.get("file_count")
        try:
            parsed_count = int(str(raw_count)) if raw_count is not None else (len(included_in_package_ids) + 1)
        except (ValueError, TypeError):
            parsed_count = len(included_in_package_ids) + 1
        package_snapshot = PackageContextSnapshot(
            package_asset_id=package_asset.id,
            package_checksum_sha256=package_asset.checksum_sha256,
            file_count=parsed_count,
            included_files=files_list,
            needs_rebuild=bool(p_prov.get("needs_rebuild", False)),
            package_hash=str(p_prov.get("package_hash", package_asset.checksum_sha256)),
        )

    # 7. Resolve Listing Draft & Etsy Draft State
    listing: ListingDraft | None = (
        await _maybe_await(uow.listing_drafts.get_by_workflow(workflow_id))
        if hasattr(uow, "listing_drafts") and hasattr(uow.listing_drafts, "get_by_workflow")
        else None
    )
    etsy_snapshot: EtsyDraftContextSnapshot | None = None
    if listing is not None:
        meta_sync = "not_dispatched"
        if listing.etsy_listing_id:
            meta_sync = "synced" if listing.etsy_dispatch_status == "completed" else "out_of_sync"

        img_sync = "not_dispatched"
        if listing.etsy_listing_id:
            img_sync = (
                "synced"
                if len(listing.etsy_image_ids) == len(active_mockups) and active_mockups
                else "out_of_sync"
            )

        files_sync = "not_dispatched"
        if listing.etsy_listing_id:
            files_sync = (
                "synced"
                if (listing.etsy_file_ids or listing.etsy_file_id)
                and (not package_snapshot or not package_snapshot.needs_rebuild)
                else "out_of_sync"
            )

        etsy_snapshot = EtsyDraftContextSnapshot(
            etsy_listing_id=listing.etsy_listing_id,
            etsy_state=listing.etsy_state,
            dispatch_status=listing.etsy_dispatch_status,
            metadata_sync_status=meta_sync,
            images_sync_status=img_sync,
            files_sync_status=files_sync,
            attributes_sync_status="synced" if listing.taxonomy_id else "out_of_sync",
            last_verified_at=listing.etsy_verified_at.isoformat()
            if listing.etsy_verified_at
            else None,
        )

    # 8. Compute Context Hashes
    c_hash = compute_concept_context_hash(workflow_id, concept_snapshot)
    a_hash = compute_artwork_context_hash(c_hash, artwork_snapshot)
    p_hash = compute_production_context_hash(a_hash, production_snapshot)
    v_hash = compute_variant_set_hash(p_hash, included_checksums)
    m_hash = compute_mockup_set_hash(p_hash, mockup_ids, template_ids)
    l_hash = compute_listing_context_hash(
        p_hash,
        v_hash,
        package_snapshot.file_count if package_snapshot else 1,
    )
    e_hash = compute_etsy_sync_hash(
        l_hash,
        m_hash,
        package_snapshot.package_checksum_sha256 if package_snapshot else None,
    )

    hashes = ContextHashes(
        concept_context_hash=c_hash,
        artwork_context_hash=a_hash,
        production_context_hash=p_hash,
        variant_set_hash=v_hash,
        mockup_set_hash=m_hash,
        listing_context_hash=l_hash,
        etsy_sync_hash=e_hash,
    )

    variants_snapshot = VariantContextSnapshot(
        active_variant_ids=active_variant_ids,
        included_in_package_ids=included_in_package_ids,
        variant_checksums=included_checksums,
        variant_set_hash=v_hash,
    )

    mockups_snapshot = MockupContextSnapshot(
        mockup_count=len(active_mockups),
        cover_mockup_asset_id=cover_id,
        mockup_asset_ids=mockup_ids,
        template_ids=template_ids,
        mockup_set_hash=m_hash,
    )

    # 9. Evaluate Staleness Graph
    stale_reasons: list[str] = []

    # Concept Status
    concept_st = ContextStatus.CURRENT if active_concept else ContextStatus.MISSING

    # Artwork Status: must match active concept
    artwork_st = ContextStatus.CURRENT
    if not approved_artwork_asset:
        artwork_st = ContextStatus.MISSING
    elif active_concept and artwork_concept_id and artwork_concept_id != active_concept.id:
        artwork_st = ContextStatus.STALE
        stale_reasons.append(
            "Selected concept was changed after artwork was generated. Please generate or approve artwork for the new concept."
        )

    # Production Status: must match approved artwork
    prod_st = ContextStatus.CURRENT
    if not master_asset:
        prod_st = ContextStatus.MISSING
    elif artwork_st == ContextStatus.STALE:
        prod_st = ContextStatus.STALE
        stale_reasons.append(
            "Production master PNG is derived from an outdated artwork version."
        )

    # Variants Status
    var_st = ContextStatus.CURRENT
    if prod_st == ContextStatus.STALE:
        var_st = ContextStatus.STALE
        stale_reasons.append("Artwork color variants were derived from an outdated master PNG.")

    # Mockups Status
    mock_st = ContextStatus.CURRENT
    if not active_mockups:
        mock_st = ContextStatus.MISSING
    elif prod_st == ContextStatus.STALE:
        mock_st = ContextStatus.STALE
        stale_reasons.append(
            "Mockups were rendered with an older artwork design. Please re-composite mockups."
        )

    # Listing Status
    listing_st = ContextStatus.CURRENT
    if not listing:
        listing_st = ContextStatus.MISSING
    elif prod_st == ContextStatus.STALE or artwork_st == ContextStatus.STALE:
        listing_st = ContextStatus.STALE
        stale_reasons.append(
            "Listing copy was generated from an older concept or artwork. Please regenerate listing details."
        )
    elif listing.listing_context_hash and listing.listing_context_hash != l_hash:
        listing_st = ContextStatus.STALE
        stale_reasons.append(
            "Listing copy context hash changed due to upstream modifications."
        )

    # Package Status
    pkg_st = ContextStatus.CURRENT
    if not package_snapshot or not package_asset:
        pkg_st = ContextStatus.MISSING
    elif prod_st == ContextStatus.STALE or package_snapshot.needs_rebuild:
        pkg_st = ContextStatus.STALE
        stale_reasons.append(
            "Customer download package is out of date. Please rebuild customer package."
        )

    # Etsy Sync Status
    etsy_st = ContextStatus.CURRENT
    if not etsy_snapshot or not etsy_snapshot.etsy_listing_id:
        etsy_st = ContextStatus.MISSING
    elif (
        listing_st == ContextStatus.STALE
        or mock_st == ContextStatus.STALE
        or pkg_st == ContextStatus.STALE
    ):
        etsy_st = ContextStatus.STALE
        stale_reasons.append(
            "Etsy draft listing has local changes that have not been synced to Etsy."
        )

    staleness_report = StalenessReport(
        concept_status=concept_st,
        artwork_status=artwork_st,
        production_status=prod_st,
        variants_status=var_st,
        mockups_status=mock_st,
        listing_status=listing_st,
        package_status=pkg_st,
        etsy_sync_status=etsy_st,
        stale_reasons=stale_reasons,
    )

    return WorkflowContextSnapshot(
        workflow_id=workflow_id,
        workflow_name=workflow.name,
        workflow_state=workflow.state,
        workflow_version=workflow.version,
        owner_id=owner_id,
        concept=concept_snapshot,
        artwork=artwork_snapshot,
        production=production_snapshot,
        variants=variants_snapshot,
        mockups=mockups_snapshot,
        package=package_snapshot,
        etsy_draft=etsy_snapshot,
        hashes=hashes,
        staleness=staleness_report,
    )


async def invalidate_downstream(
    workflow_id: uuid.UUID,
    changed_source: str,  # "concept" | "artwork" | "master" | "variants" | "mockups" | "listing"
    source_id: uuid.UUID | None,
    uow: UnitOfWork,
) -> StalenessReport:
    """Invalidate downstream artifacts non-destructively and record audit transitions."""
    logger.info(
        "invalidating_downstream_context",
        workflow_id=str(workflow_id),
        changed_source=changed_source,
        source_id=str(source_id) if source_id else None,
    )

    workflow = await _maybe_await(uow.workflows.get(workflow_id))
    if not workflow:
        raise EntityNotFoundError("ProductWorkflow", workflow_id)

    assets = await _maybe_await(uow.assets.list_for_workflow(workflow_id))
    listing = (
        await _maybe_await(uow.listing_drafts.get_by_workflow(workflow_id))
        if hasattr(uow, "listing_drafts") and hasattr(uow.listing_drafts, "get_by_workflow")
        else None
    )

    # 1. If Concept Changed: Mark downstream assets & listing as stale
    if changed_source in ("concept", "concept_prompt"):
        for a in (assets or []):
            prov = dict(a.provenance) if isinstance(a.provenance, dict) else {}
            if prov.get("approved"):
                prov["status"] = "superseded"
                prov["superseded_by_concept_change"] = True
                a.provenance = prov
            if prov.get("asset_type") in ("mockup", "buyer_package", "variant"):
                prov["is_stale"] = True
                a.provenance = prov

        if listing:
            listing.listing_context_hash = None  # Force staleness
            l_props = (
                dict(listing.etsy_properties)
                if isinstance(listing.etsy_properties, dict)
                else {}
            )
            l_props["stale_reason"] = "concept_changed"
            listing.etsy_properties = l_props

    # 2. If Artwork Changed: Mark production, variants, mockups, package as stale
    elif changed_source == "artwork":
        for a in (assets or []):
            prov = dict(a.provenance) if isinstance(a.provenance, dict) else {}
            if prov.get("asset_type") in ("mockup", "buyer_package", "variant"):
                prov["is_stale"] = True
                prov["needs_rebuild"] = True
                a.provenance = prov

        if listing:
            listing.listing_context_hash = None
            l_props = (
                dict(listing.etsy_properties)
                if isinstance(listing.etsy_properties, dict)
                else {}
            )
            l_props["stale_reason"] = "artwork_changed"
            listing.etsy_properties = l_props

    # 3. If Master PNG Changed
    elif changed_source == "master":
        for a in (assets or []):
            prov = dict(a.provenance) if isinstance(a.provenance, dict) else {}
            if prov.get("asset_type") in ("mockup", "buyer_package"):
                prov["is_stale"] = True
                prov["needs_rebuild"] = True
                a.provenance = prov

    # 4. If Variants Changed
    elif changed_source == "variants":
        for a in (assets or []):
            prov = dict(a.provenance) if isinstance(a.provenance, dict) else {}
            if (
                prov.get("asset_type") == "buyer_package"
                or a.storage_key.endswith(".zip")
            ):
                prov["needs_rebuild"] = True
                a.provenance = prov

    # Record Audit Event
    if hasattr(uow, "audit") and hasattr(uow.audit, "record"):
        await _maybe_await(
            uow.audit.record(
                action=AuditAction.WORKFLOW_TRANSITION,
                entity_type="ProductWorkflow",
                entity_id=workflow_id,
                actor=str(workflow.owner_id),
                summary=f"Downstream context invalidated due to {changed_source} change.",
                metadata={
                    "workflow_id": str(workflow_id),
                    "changed_source": changed_source,
                    "source_id": str(source_id) if source_id else None,
                },
            )
        )

    if hasattr(uow, "session") and hasattr(uow.session, "flush"):
        await _maybe_await(uow.session.flush())

    return (await resolve_current_workflow_context(workflow_id, workflow.owner_id, uow)).staleness
