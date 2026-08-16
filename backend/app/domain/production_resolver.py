"""Authoritative production asset resolution and user mockup filtering.

Provides single-source domain logic for identifying production master PNGs
and filtering active user-template mockups.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from app.application.unit_of_work import UnitOfWork
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
    if prov.get("default_mockup"):
        return False
    return True


def filter_active_user_mockups(
    assets: Sequence[Asset],
    master_asset_id: uuid.UUID | None = None,
) -> list[Asset]:
    """Filter and sort active user mockups for a workflow / master PNG."""
    valid_mockups = [a for a in assets if is_valid_user_mockup_asset(a)]

    if master_asset_id is not None:
        valid_mockups = [
            a for a in valid_mockups
            if a.derived_from_id == master_asset_id
            or (a.provenance and str(a.provenance.get("source_asset_id")) == str(master_asset_id))
        ]

    def _mockup_sort_key(a: Asset):
        is_cov = bool(a.provenance.get("is_cover", False)) if a.provenance else False
        order = int(str(a.provenance.get("listing_order", 999) or 999)) if a.provenance else 999
        created_dt = a.created_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        return (order, 0 if is_cov else 1, -created_dt.timestamp())

    return sorted(valid_mockups, key=_mockup_sort_key)


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
    sorted_assets = sorted(assets, key=lambda a: a.created_at or datetime.min, reverse=True)
    master_asset = next(
        (
            a for a in sorted_assets
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

    # 3. Fallback to newest artwork candidate asset
    artwork_assets = [
        a for a in sorted_assets
        if a.artwork_job_id is not None
        and not is_valid_user_mockup_asset(a)
        and "/mockups/" not in a.storage_key
    ]
    return artwork_assets[0] if artwork_assets else None
