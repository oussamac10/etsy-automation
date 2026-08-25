export interface StalenessReport {
  concept_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  artwork_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  production_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  variants_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  mockups_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  listing_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  package_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  etsy_sync_status: "CURRENT" | "STALE" | "SUPERSEDED" | "MISSING" | "LEGACY_UNVERIFIED";
  is_any_stale: boolean;
  stale_reasons: string[];
}

export interface ContextHashes {
  concept_context_hash: string;
  artwork_context_hash: string;
  production_context_hash: string;
  variant_set_hash: string;
  mockup_set_hash: string;
  listing_context_hash: string;
  etsy_sync_hash: string;
}

export interface WorkflowContextResponse {
  workflow_id: string;
  workflow_name: string;
  workflow_state: string;
  workflow_version: number;
  active_concept_id?: string | null;
  active_concept_title?: string | null;
  approved_artwork_asset_id?: string | null;
  production_master_asset_id?: string | null;
  active_mockup_count: number;
  buyer_package_asset_id?: string | null;
  etsy_listing_id?: string | null;
  hashes: ContextHashes;
  staleness: StalenessReport;
}
