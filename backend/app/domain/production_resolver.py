"""Authoritative production asset resolution and user mockup filtering.

Provides single-source domain logic for identifying production master PNGs
and filtering active user-template mockups with strict provenance checks.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.application.unit_of_work import UnitOfWork
from app.domain.workflow import ApprovalDecision, ApprovalGate
from app.infrastructure.models import Asset


def is_valid_user_mockup_asset(asset: Asset) -> bool:
    """Determine whether an asset is a valid, active user-uploaded template mockup."""
    prov = asset.provenance or {}
    if prov.get("asset_type") != "mockup":
        return False
    if prov.get("source") != "user_template":
        return False
    if not (prov.get("template_id") or prov.get("template_storage_key")):
        return False
    if prov.get("provider") in ("fake", "default"):
        return False
    if prov.get("status") in ("superseded", "deleted"):
        return False
    return not bool(prov.get("default_mockup"))


def filter_active_user_mockups(
    assets: Sequence[Asset],
    master_asset_id: uuid.UUID | None = None,
) -> list[Asset]:
    """Filter and sort active user mockups for a workflow / master PNG."""
    valid_mockups = [a for a in assets if is_valid_user_mockup_asset(a)]

    if master_asset_id is not None:
        valid_mockups = [
            a
            for a in valid_mockups
            if a.derived_from_id == master_asset_id
            or (a.provenance and str(a.provenance.get("source_asset_id")) == str(master_asset_id))
        ]

    def _mockup_sort_key(a: Asset) -> tuple[int, int, float]:
        is_cov = bool(a.provenance.get("is_cover", False)) if a.provenance else False
        order = int(str(a.provenance.get("listing_order", 999) or 999)) if a.provenance else 999
        created_dt = a.created_at or datetime(1970, 1, 1, tzinfo=UTC)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=UTC)
        return (0 if is_cov else 1, order, -created_dt.timestamp())

    sorted_list = sorted(valid_mockups, key=_mockup_sort_key)

    deduped: list[Asset] = []
    seen_template_keys: set[str] = set()
    for a in sorted_list:
        prov = a.provenance or {}
        prod_type = str(prov.get("product_type", "")).lower().strip()
        tpl_id = str(prov.get("template_id", "") or prov.get("template_storage_key", "")).strip()
        key = f"{prod_type}::{tpl_id}" if tpl_id else str(a.id)
        if key in seen_template_keys:
            continue
        seen_template_keys.add(key)
        deduped.append(a)

    return deduped


async def get_production_master_asset(
    uow: UnitOfWork,
    workflow_id: uuid.UUID,
    master_asset_id: uuid.UUID | None = None,
) -> Asset | None:
    """Authoritatively resolve the production master PNG for a workflow."""
    if master_asset_id is not None:
        candidate = await uow.assets.get(master_asset_id)
        if candidate and candidate.workflow_id == workflow_id:
            return candidate

    # 1. Inspect production jobs (newest first)
    jobs = await uow.production_jobs.list_for_workflow(workflow_id)
    if jobs:
        for job in jobs:
            if job.output_asset_id:
                candidate = await uow.assets.get(job.output_asset_id)
                if candidate and candidate.workflow_id == workflow_id:
                    return candidate

    # 2. Inspect workflow assets for master.png or etsy-png-standard profile (non-mockup)
    assets = await uow.assets.list_for_workflow(workflow_id)

    def _sort_key(a: Any) -> float:
        dt = getattr(a, "created_at", None)
        if dt is None:
            return 0.0
        return dt.timestamp() if hasattr(dt, "timestamp") else 0.0

    sorted_assets = sorted(assets, key=_sort_key, reverse=True)
    master_asset = next(
        (
            a
            for a in sorted_assets
            if (
                a.storage_key.endswith("/master.png")
                or (a.provenance and a.provenance.get("profile") == "etsy-png-standard")
            )
            and not is_valid_user_mockup_asset(a)
            and "/mockups/" not in a.storage_key
        ),
        None,
    )
    if master_asset:
        return master_asset

    # 3. Check for approved Gate 2 artwork asset
    approvals = await uow.approvals.history(workflow_id, gate=ApprovalGate.ARTWORK_APPROVAL)
    approved_gate2 = next((a for a in approvals if a.decision == ApprovalDecision.APPROVED), None)
    if approved_gate2 and approved_gate2.target_id:
        target = await uow.assets.get(approved_gate2.target_id)
        if target and target.workflow_id == workflow_id:
            return target

    # 4. Fallback to candidate artwork asset explicitly marked approved
    approved_artwork = next(
        (
            a
            for a in sorted_assets
            if (a.artwork_job_id is not None or (a.provenance and a.provenance.get("kind") == "candidate_artwork"))
            and (a.provenance and a.provenance.get("approved"))
            and not is_valid_user_mockup_asset(a)
            and "/mockups/" not in a.storage_key
        ),
        None,
    )
    if approved_artwork:
        return approved_artwork

    # 5. Last resort candidate artwork (if workflow is in early stage before Gate 2 approval)
    artwork_assets = [
        a
        for a in sorted_assets
        if a.artwork_job_id is not None
        and not is_valid_user_mockup_asset(a)
        and "/mockups/" not in a.storage_key
    ]
    return artwork_assets[0] if artwork_assets else None
