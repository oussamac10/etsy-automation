export type EtsyConnectionState = 'connected' | 'refresh_required' | 'reauthorization_required' | 'disconnected';

export type EtsyTokenHealth = 'valid' | 'refresh_required' | 'reauthorization_required' | 'disconnected';

export type EtsyDispatchStatus =
  | 'not_started'
  | 'queued'
  | 'creating_listing'
  | 'uploading_images'
  | 'uploading_file'
  | 'uploading_files'
  | 'applying_attributes'
  | 'completed'
  | 'draft_removed'
  | 'failed';

export interface EtsyDispatchStepInfo {
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  uploaded_count?: number;
  total_count?: number | null;
  error?: string | null;
}

export interface EtsyConnectionStatus {
  connected: boolean;
  shop_id?: string | null;
  shop_name?: string | null;
  connection_status: EtsyConnectionState;
  granted_scopes: string[];
  token_health: EtsyTokenHealth;
  token_expires_at?: string | null;
  last_refreshed_at?: string | null;
}

export interface EtsyConnectResponse {
  authorization_url: string;
}

export interface EtsyDraftDispatchResponse {
  workflow_id: string;
  dispatch_status: EtsyDispatchStatus;
  current_step?: string | null;
  etsy_listing_id?: string | null;
  etsy_listing_url?: string | null;
  etsy_state?: string | null;
  etsy_shop_id?: string | null;
  etsy_image_ids?: string[];
  etsy_file_id?: string | null;
  etsy_file_ids?: string[];
  taxonomy_id?: number | null;
  taxonomy_path?: string | null;
  error_message?: string | null;
  last_synced_at?: string | null;
  steps?: Record<string, EtsyDispatchStepInfo>;
}
