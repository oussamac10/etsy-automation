export type VariantType =
  | "dark_shirt"
  | "light_shirt"
  | "black_accent"
  | "white_accent"
  | "custom";

export type VariantStatus =
  | "generating"
  | "ready"
  | "approved"
  | "rejected"
  | "failed";

export interface VariantValidationReport {
  is_valid: boolean;
  format?: string;
  mode?: string;
  width?: number;
  height?: number;
  has_real_alpha?: boolean;
  min_alpha?: number;
  checkerboard_free?: boolean;
  source_composition_preserved?: boolean;
  target_color?: string;
  method?: string;
  error?: string;
}

export interface ArtworkVariantItem {
  id: string;
  workflow_id: string;
  derived_from_id: string | null;
  storage_key: string;
  mime_type: string;
  byte_size: number;
  checksum_sha256: string;
  width: number | null;
  height: number | null;
  has_alpha: boolean | null;
  variant_type: VariantType | string;
  variant_status: VariantStatus | string;
  title: string;
  custom_color: string | null;
  custom_instructions: string | null;
  prompt_version: string | null;
  url: string | null;
  include_in_buyer_package?: boolean;
  source_outdated?: boolean;
  validation_report?: VariantValidationReport | null;
  created_at: string;
}

export interface CreateArtworkVariantPayload {
  variant_type: VariantType | string;
  custom_color?: string | null;
  target_color?: string | null;
  darkness_threshold?: number | null;
  custom_instructions?: string | null;
}

export interface PackageFileItem {
  type: string;
  name: string;
  filename: string;
  byte_size: number;
  included: boolean;
  status: "ready" | "outdated" | "unapproved" | "missing" | string;
  asset_id: string | null;
}

export interface BuyerPackagePreviewResponse {
  workflow_id: string;
  files: PackageFileItem[];
  included_count: number;
  estimated_total_bytes: number;
  needs_rebuild: boolean;
  etsy_files_out_of_sync: boolean;
  package_asset?: Record<string, unknown> | null;
  package_download_url?: string | null;
}

