import type { Asset } from '~/types/workflow';

export type RiskLevel = 'low' | 'medium' | 'high' | 'unknown';

export interface TrademarkFinding {
  mark_text?: string;
  matched_mark?: string;
  searched_phrase?: string;
  match_type?: string;
  serial_number?: string | null;
  registration_number?: string | null;
  status?: string;
  is_live: boolean;
  goods_services?: string | null;
  classes?: string[];
  owner?: string | null;
  filing_date?: string | null;
  registration_date?: string | null;
  source_url?: string | null;
  tsdr_verified?: boolean;
  risk_reason?: string;
  recommended_action?: string;
}

export interface IpFindingsReport {
  screening_source?: 'USPTO_LOCAL_INDEX' | 'USPTO_LOCAL_INDEX_TSDR_VERIFIED' | 'USPTO_LOCAL_INDEX_TSDR_UNAVAILABLE' | 'local_defense_registry' | string;
  uspto_status?: 'SUCCESS' | 'UNAVAILABLE' | string;
  warning_message?: string | null;
  dataset_updated_at?: string | null;
  tsdr_status?: 'VERIFIED' | 'UNAVAILABLE' | 'NOT_QUERIED' | string;
  tsdr_verified_at?: string | null;
  scanned_phrases?: string[];
  searched_phrases?: string[];
  risk_level?: RiskLevel;
  match_count?: number;
  total_matches?: number;
  live_pod_matches?: number;
  live_other_matches?: number;
  dead_matches?: number;
  matches?: TrademarkFinding[];
  findings?: Record<string, unknown>[];
  reasons?: string[];
  reviewed_at?: string;
  disclaimer?: string;
  requires_acknowledgement?: boolean;
  blocks_approval?: boolean;
}

export interface ListingVersionSnapshot {
  version: number;
  title: string;
  description: string;
  tags: string[];
  ip_risk_level?: string;
  created_at?: string;
  source?: 'ai_generated' | 'manual' | 'initial';
}

export interface ListingDraft {
  id: string;
  workflow_id: string;
  title: string;
  description: string;
  tags: string[];
  taxonomy_id?: number | null;
  taxonomy_path?: string | null;
  price_minor_units?: number | null;
  currency?: string | null;
  quantity?: number;
  sku?: string | null;
  shop_section_id?: string | null;
  shop_section_name?: string | null;
  should_auto_renew?: boolean;
  etsy_properties?: Record<string, any>;
  primary_mockup_asset_id?: string | null;
  shopping_cart_summary?: string | null;
  ai_disclosure?: string | null;
  licence_text?: string | null;
  customer_instructions?: string | null;
  ip_reviewed_phrase?: string | null;
  ip_risk_level: RiskLevel;
  ip_findings: IpFindingsReport;
  ip_acknowledged_at?: string | null;
  ip_acknowledged_by?: string | null;
  version: number;
  package_asset?: Asset | null;
  package_download_url?: string | null;
  history?: ListingVersionSnapshot[];
  tag_history?: string[];
  etsy_shop_id?: string | null;
  etsy_listing_id?: string | null;
  etsy_listing_url?: string | null;
  etsy_state?: string | null;
  etsy_image_ids?: string[];
  etsy_file_id?: string | null;
  etsy_file_ids?: string[];
  etsy_dispatch_status?: string | null;
  etsy_draft_created_at?: string | null;
  etsy_last_synced_at?: string | null;
  etsy_failure_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpdateListingPayload {
  title: string;
  description: string;
  tags: string[];
  taxonomy_id?: number | null;
  taxonomy_path?: string | null;
  price_minor_units?: number | null;
  currency?: string | null;
  quantity?: number | null;
  sku?: string | null;
  shop_section_id?: string | null;
  shop_section_name?: string | null;
  should_auto_renew?: boolean | null;
  etsy_properties?: Record<string, any> | null;
  primary_mockup_asset_id?: string | null;
  shopping_cart_summary?: string | null;
  expected_version?: number;
}

export interface TaxonomyCategory {
  id: number;
  name: string;
  full_path: string;
  level: number;
}

export interface ShopSection {
  shop_section_id: string;
  title: string;
  rank: number;
  active_listing_count: number;
}

export interface TaxonomyProperty {
  property_id: number;
  name: string;
  is_required: boolean;
  supports_attributes: boolean;
  is_multivalued: boolean;
  possible_values: Array<{ value_id: number; name: string }>;
}

export interface PriceRecommendation {
  recommended_minor_units: number;
  currency: string;
  formatted_price: string;
  rationale: string;
  factors: string[];
}

export interface Gate3DecisionPayload {
  decision: 'approved' | 'rejected' | 'APPROVED' | 'REJECTED';
  acknowledged?: boolean;
}

