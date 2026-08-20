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
