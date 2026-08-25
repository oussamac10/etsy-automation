"""Domain models and pure functions for workflow context, provenance, and staleness detection.

Establishes the canonical dependency chain:
Workflow -> Selected Concept -> Approved Artwork -> Master PNG -> Variants / Mockups / Listing Copy -> Buyer Package -> Etsy Draft

Guarantees:
1. Deterministic provenance tracking across all workflow stages.
2. Context hash calculation for every derived artifact.
3. Central staleness evaluation graph.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContextStatus(str, Enum):
    """Lifecycle status of a derived artifact in relation to the current workflow context."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    MISSING = "MISSING"
    LEGACY_UNVERIFIED = "LEGACY_UNVERIFIED"


class FieldProvenance(str, Enum):
    """Provenance tracking for individual listing copy fields."""

    GENERATED = "generated"
    MANUALLY_EDITED = "manually_edited"
    MANUAL_STALE = "manual_stale"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ConceptContextSnapshot:
    """Snapshot of the active approved concept."""

    id: uuid.UUID
    version: int
    title: str
    description: str
    target_buyer: str | None
    niche: str
    seasonality: str | None
    visual_direction: str | None
    slogan: str | None
    keywords: list[str] = field(default_factory=list)
    intended_product_uses: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ArtworkContextSnapshot:
    """Snapshot of the approved artwork asset linked to the active concept."""

    asset_id: uuid.UUID | None
    concept_id: uuid.UUID | None
    is_approved: bool
    width: int
    height: int
    dpi: int
    has_transparent_pixels: bool
    checksum_sha256: str | None
    visual_summary: str | None


@dataclass(frozen=True, slots=True)
class ProductionContextSnapshot:
    """Snapshot of the production deliverable and master PNG."""

    master_asset_id: uuid.UUID | None
    job_id: uuid.UUID | None
    width: int
    height: int
    dpi: int
    checksum_sha256: str | None
    has_transparent_background: bool
    qa_passed: bool | None
    color_profile: str = "sRGB"


@dataclass(frozen=True, slots=True)
class VariantContextSnapshot:
    """Snapshot of active approved artwork color variants."""

    active_variant_ids: list[uuid.UUID] = field(default_factory=list)
    included_in_package_ids: list[uuid.UUID] = field(default_factory=list)
    variant_checksums: list[str] = field(default_factory=list)
    variant_set_hash: str = ""


@dataclass(frozen=True, slots=True)
class MockupContextSnapshot:
    """Snapshot of active user template mockups."""

    mockup_count: int
    cover_mockup_asset_id: uuid.UUID | None
    mockup_asset_ids: list[uuid.UUID] = field(default_factory=list)
    template_ids: list[str] = field(default_factory=list)
    mockup_set_hash: str = ""


@dataclass(frozen=True, slots=True)
class PackageContextSnapshot:
    """Snapshot of the buyer download ZIP package."""

    package_asset_id: uuid.UUID | None
    package_checksum_sha256: str | None
    file_count: int
    included_files: list[str] = field(default_factory=list)
    needs_rebuild: bool = False
    package_hash: str = ""


@dataclass(frozen=True, slots=True)
class EtsyDraftContextSnapshot:
    """Snapshot of the Etsy draft listing state."""

    etsy_listing_id: str | None
    etsy_state: str | None
    dispatch_status: str
    metadata_sync_status: str  # "synced" | "out_of_sync" | "not_dispatched"
    images_sync_status: str
    files_sync_status: str
    attributes_sync_status: str
    last_verified_at: str | None


@dataclass(frozen=True, slots=True)
class StalenessReport:
    """Detailed staleness breakdown for all downstream workflow stages."""

    concept_status: ContextStatus
    artwork_status: ContextStatus
    production_status: ContextStatus
    variants_status: ContextStatus
    mockups_status: ContextStatus
    listing_status: ContextStatus
    package_status: ContextStatus
    etsy_sync_status: ContextStatus
    stale_reasons: list[str] = field(default_factory=list)

    @property
    def is_any_stale(self) -> bool:
        return any(
            status in (ContextStatus.STALE, ContextStatus.SUPERSEDED)
            for status in (
                self.artwork_status,
                self.production_status,
                self.variants_status,
                self.mockups_status,
                self.listing_status,
                self.package_status,
                self.etsy_sync_status,
            )
        )


@dataclass(frozen=True, slots=True)
class ContextHashes:
    """Deterministic cryptographic context hashes across the workflow lifecycle."""

    concept_context_hash: str
    artwork_context_hash: str
    production_context_hash: str
    variant_set_hash: str
    mockup_set_hash: str
    listing_context_hash: str
    etsy_sync_hash: str


@dataclass(frozen=True, slots=True)
class WorkflowContextSnapshot:
    """Authoritative normalized snapshot of the entire workflow context."""

    workflow_id: uuid.UUID
    workflow_name: str
    workflow_state: str
    workflow_version: int
    owner_id: uuid.UUID
    concept: ConceptContextSnapshot | None
    artwork: ArtworkContextSnapshot | None
    production: ProductionContextSnapshot | None
    variants: VariantContextSnapshot
    mockups: MockupContextSnapshot
    package: PackageContextSnapshot | None
    etsy_draft: EtsyDraftContextSnapshot | None
    hashes: ContextHashes
    staleness: StalenessReport


# ---------------------------------------------------------------------------
# Deterministic Hash Calculation Pure Functions
# ---------------------------------------------------------------------------


def compute_concept_context_hash(
    workflow_id: uuid.UUID,
    concept: ConceptContextSnapshot | None,
) -> str:
    """Compute sha256 hash for active concept context."""
    if concept is None:
        return ""
    payload = {
        "workflow_id": str(workflow_id),
        "concept_id": str(concept.id),
        "concept_version": concept.version,
        "concept_title": concept.title.strip(),
        "concept_slogan": (concept.slogan or "").strip(),
        "niche": concept.niche.strip(),
        "intended_uses": sorted(concept.intended_product_uses),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_artwork_context_hash(
    concept_context_hash: str,
    artwork: ArtworkContextSnapshot | None,
) -> str:
    """Compute sha256 hash for approved artwork context."""
    if not artwork or not artwork.asset_id:
        return ""
    payload = {
        "concept_context_hash": concept_context_hash,
        "artwork_asset_id": str(artwork.asset_id),
        "artwork_checksum": artwork.checksum_sha256 or "",
        "width": artwork.width,
        "height": artwork.height,
        "has_transparent_pixels": artwork.has_transparent_pixels,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_production_context_hash(
    artwork_context_hash: str,
    production: ProductionContextSnapshot | None,
) -> str:
    """Compute sha256 hash for production deliverable / master PNG."""
    if not production or not production.master_asset_id:
        return ""
    payload = {
        "artwork_context_hash": artwork_context_hash,
        "master_asset_id": str(production.master_asset_id),
        "master_checksum": production.checksum_sha256 or "",
        "width": production.width,
        "height": production.height,
        "dpi": production.dpi,
        "qa_passed": production.qa_passed,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_variant_set_hash(
    production_context_hash: str,
    included_variant_checksums: list[str],
) -> str:
    """Compute sha256 hash for selected approved color variants."""
    payload = {
        "production_context_hash": production_context_hash,
        "variant_checksums": sorted(included_variant_checksums),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_mockup_set_hash(
    production_context_hash: str,
    mockup_asset_ids: list[uuid.UUID],
    template_ids: list[str],
) -> str:
    """Compute sha256 hash for active mockups."""
    payload = {
        "production_context_hash": production_context_hash,
        "mockup_asset_ids": sorted([str(m) for m in mockup_asset_ids]),
        "template_ids": sorted(template_ids),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_listing_context_hash(
    production_context_hash: str,
    variant_set_hash: str,
    package_file_count: int,
    prompt_version: int = 1,
) -> str:
    """Compute sha256 hash for generated listing copy context."""
    if not production_context_hash:
        return ""
    payload = {
        "production_context_hash": production_context_hash,
        "variant_set_hash": variant_set_hash,
        "package_file_count": package_file_count,
        "prompt_version": prompt_version,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_etsy_sync_hash(
    listing_context_hash: str,
    mockup_set_hash: str,
    package_checksum: str | None,
) -> str:
    """Compute sha256 hash for Etsy draft dispatch state."""
    if not listing_context_hash:
        return ""
    payload = {
        "listing_context_hash": listing_context_hash,
        "mockup_set_hash": mockup_set_hash,
        "package_checksum": package_checksum or "",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
