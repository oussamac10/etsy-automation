export type MockupBlendMode =
  | "over"
  | "multiply"
  | "overlay"
  | "soft-light"
  | "screen"
  | "darken"
  | "lighten"
  | "hard-light"
  | "color-burn"
  | "color-dodge";

export interface MockupPlacement {
  id?: string;
  left_pct: number;
  top_pct: number;
  width_pct: number;
  height_pct: number;
  angle_deg: number;
  blend_mode: MockupBlendMode | string;
  artwork_source_id?: string | null;
}

export interface MockupTemplateItem {
  id: string;
  name: string;
  product_type: string;
  storage_key: string;
  url?: string;
  preview_url?: string;
  placement: MockupPlacement;
  placements?: MockupPlacement[];
  width: number;
  height: number;
  created_at: string;
}

export type MockupTemplate = MockupTemplateItem;

export interface MockupAsset {
  id: string;
  workflow_id: string;
  derived_from_id?: string | null;
  storage_key: string;
  mime_type: string;
  byte_size: number;
  checksum_sha256: string;
  width: number;
  height: number;
  has_alpha?: boolean;
  has_transparent_pixels?: boolean;
  quality_check?: Record<string, unknown>;
  provenance?: {
    phase?: number;
    asset_type?: string;
    source?: string;
    product_type?: string;
    template_id?: string | null;
    template_name?: string | null;
    template_storage_key?: string | null;
    source_asset_id?: string | null;
    placement?: MockupPlacement;
    placements?: MockupPlacement[];
    is_cover?: boolean;
    listing_order?: number;
    created_for_listing?: boolean;
    [key: string]: unknown;
  };
  created_at?: string;
  url?: string;
}

export interface CompositeMockupRequest {
  workflow_id: string;
  product_type: string;
  template_id?: string | null;
  template_name?: string | null;
  template_image_base64?: string | null;
  save_as_template?: boolean;
  placement?: MockupPlacement;
  placements?: MockupPlacement[];
  is_cover?: boolean;
  target_asset_id?: string | null;
  master_asset_id?: string | null;
}

export interface CompositeMockupResponse {
  mockup_url: string;
  asset_id: string;
  product_type: string;
  template_id?: string | null;
  template_name?: string | null;
  is_cover?: boolean;
  listing_order?: number;
  width?: number;
  height?: number;
  format?: string;
}
