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
  created_at: string;
}

export interface CreateArtworkVariantPayload {
  variant_type: VariantType | string;
  custom_color?: string | null;
  custom_instructions?: string | null;
}
