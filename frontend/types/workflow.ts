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
