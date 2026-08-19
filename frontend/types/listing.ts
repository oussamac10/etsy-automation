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
  price_minor_units?: number | null;
  currency?: string | null;
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
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpdateListingPayload {
  title: string;
  description: string;
  tags: string[];
  expected_version?: number;
}

export interface Gate3DecisionPayload {
  decision: 'approved' | 'rejected';
  acknowledged?: boolean;
}
