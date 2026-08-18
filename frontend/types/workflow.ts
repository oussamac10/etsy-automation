export interface Asset {
  id: string;
  workflow_id: string;
  storage_key: string;
  mime_type: string;
  byte_size: number;
  checksum_sha256?: string | null;
  width?: number | null;
  height?: number | null;
  has_alpha?: boolean | null;
  has_transparent_pixels?: boolean | null;
  provenance?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface WorkflowSummary {
  id: string;
  owner_id: string;
  idea_mode: string;
  name: string;
  target_marketplace: string;
  target_country: string;
  output_language: string;
  target_buyer?: string | null;
  intended_product_uses?: string[];
  state: string;
  version: number;
  created_at: string;
  updated_at: string;
}
