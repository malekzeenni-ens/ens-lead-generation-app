export interface Campaign {
  id: string;
  name: string;
  description: string | null;
  segment: string;
  primary_location: string;
  radius_miles: number;
  keywords: string[];
  exclusion_keywords: string[];
  product_categories: string[];
  product_family_id: string | null;
  discovery_sources: string[];
  weekly_shortlist_size: number;
  minimum_score_threshold: number;
  preferred_channels: string[];
  offer_settings: Record<string, boolean>;
  discovery_mode: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SourceObservation {
  id: string;
  source_name: string;
  source_type: string;
  field_name: string;
  observed_value: string;
  classification: string;
  source_url: string | null;
  collection_method: string;
  collected_at: string;
}

export interface StageEvent {
  id: string;
  previous_stage: string | null;
  new_stage: string;
  actor: string;
  reason: string | null;
  created_at: string;
}

export interface LeadNote {
  id: string;
  content: string;
  actor: string;
  created_at: string;
}

export interface FollowUp {
  id: string;
  follow_up_type: string;
  due_date: string;
  status: string;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Communication {
  id: string;
  channel: string;
  subject: string | null;
  content: string;
  draft_status: string;
  approval_status: string;
  sent_status: string;
  sent_at: string | null;
  user_confirmed: boolean;
  external_message_id: string | null;
  response_status: string;
  created_at: string;
}

export interface SuppressionRecord {
  id: string;
  suppression_type: string;
  reason: string;
  source: string;
  notes: string | null;
  active: boolean;
  effective_at: string;
  lifted_at: string | null;
}

export interface Lead {
  id: string;
  business_name: string;
  segment: string;
  location: string;
  website: string | null;
  social_profile: string | null;
  phone_number: string | null;
  public_email: string | null;
  social_identities: SocialIdentity[];
  contact_classification: string;
  pipeline_stage: string;
  suppressed: boolean;
  estimated_order_value: number | null;
  quote_value: number | null;
  won_value: number | null;
  potential_recurrence: string | null;
  lost_reason: string | null;
  mock_up_status: string;
  sample_status: string;
  quote_status: string;
  retention_review_date: string | null;
  current_score: number | null;
  score_updated_at: string | null;
  campaign_ids: string[];
  sources: SourceObservation[];
  stage_events: StageEvent[];
  notes: LeadNote[];
  follow_ups: FollowUp[];
  communications: Communication[];
  suppression_records: SuppressionRecord[];
  created_at: string;
  updated_at: string;
}

export interface SocialIdentity {
  id: string;
  platform: string;
  profile_url: string;
  normalized_handle: string;
  source_url: string | null;
  classification: string;
  collected_at: string;
}

export interface OperationsSummary {
  campaigns: number;
  active_campaigns: number;
  leads: number;
  suppressed_leads: number;
  review_required: number;
  open_follow_ups: number;
  due_today: number;
  overdue: number;
  due_this_week: number;
  products: number;
  scored_leads: number;
  shortlisted_this_week: number;
  pipeline: Record<string, number>;
}

export interface WorkspaceSettings {
  retention_review_days: number;
  follow_up_window_days: number;
  default_campaign_radius_miles: number;
  default_weekly_shortlist_size: number;
}

export interface Diagnostics {
  api_status: string;
  database_status: string;
  schema_version: string;
  database_size_bytes: number;
  journal_mode: string;
  foreign_keys_enabled: boolean;
  data_directory: string;
  log_directory: string;
  campaigns: number;
  leads: number;
  audit_events: number;
  backups: number;
  products: number;
  score_runs: number;
  shortlists: number;
  campaign_runs: number;
  discovery_candidates: number;
  provider_mode: string;
  outbound_messaging: string;
}

export interface BackupResult {
  backup_path: string;
  manifest_path: string;
  checksum_sha256: string;
  integrity_result: string;
  schema_version: string;
  application_version: string;
  created_at: string;
}

export interface VerificationResult {
  valid: boolean;
  checksum_matches: boolean;
  integrity_result: string;
  schema_version: string;
}

export interface ApiErrorShape {
  code: string;
  message: string;
  details: Record<string, unknown>;
  correlation_id: string;
}

export interface Product {
  id: string;
  shopify_handle: string | null;
  name: string;
  category: string;
  description: string;
  target_segments: string[];
  example_use_cases: string[];
  image_reference: string | null;
  active: boolean;
  pricing_guidance: string | null;
  sample_eligible: boolean;
  source: string;
  variant_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductFamily {
  id: string;
  name: string;
  description: string | null;
  products: Product[];
  created_at: string;
  updated_at: string;
}

export interface Template {
  id: string;
  topic: string;
  subject: string;
  body: string;
  product_family_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ShopifyImportResult {
  filename: string;
  rows_read: number;
  products_created: number;
  products_updated: number;
  products_skipped: number;
  issues: Array<{ handle: string | null; message: string }>;
}

export interface ScoringWeights {
  business_relevance: number;
  activity: number;
  product_fit: number;
  local_relevance: number;
  commercial_potential: number;
  reach_credibility: number;
  contactability: number;
}

export interface ScoringProfile {
  id: string;
  name: string;
  segment: string;
  version: number;
  weights: ScoringWeights;
  active: boolean;
  created_at: string;
}

export interface ProductMatch {
  product_id: string;
  product_name: string;
  category: string;
  match_score: number;
  reason: string;
  evidence: string[];
  rule_based: boolean;
}

export interface ScoreBreakdown {
  category: string;
  points_awarded: number;
  points_available: number;
  evidence_used: string[];
  missing_evidence: string[];
  ai_inference: null;
}

export interface ScoreRun {
  id: string;
  lead_id: string;
  campaign_id: string;
  profile_id: string;
  profile_name: string;
  profile_version: number;
  rule_version: string;
  campaign_run_id: string | null;
  input_fingerprint: string | null;
  calculated_score: number;
  final_score: number;
  manual_override: boolean;
  override_reason: string | null;
  breakdown: ScoreBreakdown[];
  product_matches: ProductMatch[];
  created_at: string;
  overridden_at: string | null;
}

export interface ProviderAttempt {
  id: string;
  provider: string;
  status: string;
  query: string;
  request_count: number;
  response_count: number;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface DiscoveryCandidate {
  id: string;
  run_id: string;
  campaign_id: string;
  provider: string;
  provider_record_id: string;
  business_name: string;
  location: string;
  website: string | null;
  phone: string | null;
  source_url: string | null;
  place_types: string[];
  evidence: Record<string, unknown>;
  status: string;
  matched_lead_id: string | null;
  duplicate_confidence: number | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignRun {
  id: string;
  batch_id: string;
  campaign_id: string;
  campaign_name: string;
  trigger: string;
  status: string;
  phase: string;
  provider_status: string;
  query_summary: string | null;
  metrics: Record<string, number>;
  warnings: string[];
  error_code: string | null;
  error_message: string | null;
  cancellation_requested: boolean;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
  candidates: DiscoveryCandidate[];
  attempts: ProviderAttempt[];
}

export interface AutomationCapabilities {
  google_places_configured: boolean;
  instagram_configured: boolean;
  instagram_connected: boolean;
  instagram_account: string | null;
  instagram_status: string;
  website_enrichment_enabled: boolean;
  public_registries_available: boolean;
  maximum_results_per_campaign: number;
  maximum_queries_per_campaign: number;
  outbound_messaging: string;
}

export interface InstagramProfilePreview {
  account_id: string;
  username: string;
  profile_url: string;
  business_name: string;
  biography: string | null;
  website: string | null;
  public_email: string | null;
  public_phone: string | null;
  followers_count: number | null;
  media_count: number | null;
}

export interface MetaAccount {
  page_id: string;
  page_name: string;
  instagram_account_id: string;
  instagram_username: string;
}

export interface MetaConnection {
  configured: boolean;
  connected: boolean;
  status: string;
  callback_url: string;
  graph_version: string;
  accounts: MetaAccount[];
  selected_account: MetaAccount | null;
  expires_at: string | null;
  error_message: string | null;
}

export interface MetaAuthorizationStart {
  authorization_url: string;
  expires_at: string;
}

export interface ShortlistItem {
  id: string;
  lead_id: string;
  business_name: string;
  segment: string;
  location: string;
  pipeline_stage: string;
  score: number;
  rank: number;
  decision: string;
  reason: string;
  product_matches: ProductMatch[];
  created_at: string;
  decided_at: string | null;
}

export interface Shortlist {
  id: string;
  campaign_id: string;
  campaign_name: string;
  week_start: string;
  capacity: number;
  status: string;
  items: ShortlistItem[];
  created_at: string;
  updated_at: string;
}
