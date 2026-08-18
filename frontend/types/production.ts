export interface ProductionQaReport {
  dimensions_valid?: boolean;
  width?: number;
  height?: number;
  density_dpi?: number;
  has_alpha?: boolean;
  has_transparent_pixels?: boolean;
  transparent_background_valid?: boolean;
  safe_margins_valid?: boolean;
  cropped_edges_detected?: boolean;
  color_space?: string;
  file_size_bytes?: number;
  checksum_sha256?: string;
  typography_applied?: boolean;
  exact_slogan_recorded?: string | null;
  warnings?: string[];
  qa_passed?: boolean;
}

export interface ProductionQaItem {
  label: string;
  value: string;
  passed: boolean;
}

export interface MasterAsset {
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
  provenance?: Record<string, unknown>;
  created_at: string;
  url?: string;
}

export interface ProductionJob {
  id: string;
  workflow_id: string;
  source_asset_id?: string | null;
  output_asset_id?: string | null;
  operations?: string[];
  status: string;
  idempotency_key?: string;
  attempt_count?: number;
  qa_report?: ProductionQaReport;
  qa_passed?: boolean;
  started_at?: string | null;
  completed_at?: string | null;
  failure_kind?: string | null;
  failure_message?: string | null;
  created_at?: string;
  master_asset?: MasterAsset | null;
  mockup_assets?: MasterAsset[];
  mockup_urls?: Record<string, string>;
}
