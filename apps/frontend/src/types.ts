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
  weekly_outreach_enabled: boolean;
  weekly_outreach_template_id: string | null;
  weekly_outreach_provider: "scoring" | "google_places" | "instagram" | "public_registries";
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignDraftCampaign {
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
  discovery_mode: "manual" | "scheduled" | "combined";
  weekly_outreach_enabled: boolean;
  weekly_outreach_template_id: string | null;
  weekly_outreach_provider: "scoring" | "google_places" | "instagram" | "public_registries";
  status: "active" | "paused" | "inactive";
}

export interface CampaignDraftOverrideItem {
  item_id: string;
  rule_id: string;
  field: string;
  playbook_recommendation: unknown;
  requested_value: unknown;
  impact: string;
  decision: "pending" | "confirmed" | "rejected";
}

export interface CampaignDraftOverride {
  id: string;
  draft_id: string;
  draft_version: number;
  status: "pending" | "confirmed" | "partially_confirmed" | "rejected" | "superseded";
  summary: string;
  items: CampaignDraftOverrideItem[];
  playbook_version: string;
  created_at: string;
  confirmed_at: string | null;
  rejected_at: string | null;
}

export interface CampaignDraftRevision {
  id: string;
  version: number;
  revision_source: string;
  user_instruction: string | null;
  payload: CampaignDraftCampaign | null;
  assistant_message: string;
  assumptions: string[];
  warnings: string[];
  questions: string[];
  resource_profile: "standard" | "design_software";
  model_name: string;
  prompt_version: string;
  created_at: string;
}

export interface CampaignDraft {
  id: string;
  status:
    | "generating"
    | "awaiting_input"
    | "awaiting_override_confirmation"
    | "ready"
    | "generation_failed"
    | "approved"
    | "discarded";
  original_request: string;
  campaign: CampaignDraftCampaign | null;
  assistant_message: string;
  assumptions: string[];
  warnings: string[];
  questions: string[];
  version: number;
  model_name: string;
  prompt_version: string;
  resource_profile: "standard" | "design_software";
  generation_duration_ms: number | null;
  prompt_token_count: number | null;
  output_token_count: number | null;
  approved_campaign_id: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  overrides: CampaignDraftOverride[];
  revisions: CampaignDraftRevision[];
}

export interface CampaignAssistantStatus {
  enabled: boolean;
  ollama_reachable: boolean;
  model_installed: boolean;
  model_loaded: boolean;
  model: string;
  resource_profile: "standard" | "design_software";
  protected_applications: string[];
  ready: boolean;
  message: string;
}

export interface AssistantAttachment {
  id: string;
  direction: "uploaded" | "generated";
  filename: string;
  media_type: string;
  size_bytes: number;
  processing_status: "text_extracted" | "stored_image_text_model" | "generated";
  download_url: string;
  created_at: string;
}

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  model_name: string | null;
  resource_profile: "standard" | "design_software" | null;
  generation_duration_ms: number | null;
  campaign_draft_suggested: boolean;
  attachments: AssistantAttachment[];
  created_at: string;
}

export interface AssistantConversation {
  id: string;
  title: string;
  messages: AssistantMessage[];
  created_at: string;
  updated_at: string;
}

export interface AssistantAttachmentInput {
  filename: string;
  media_type: string;
  content_base64: string;
}

export type AssistantContextKind =
  | "workspace"
  | "campaign"
  | "lead"
  | "outreach_batch"
  | "shortlist";

export interface AssistantContextSelection {
  kind: AssistantContextKind;
  id: string | null;
}

export interface CampaignDraftApprovalResult {
  draft: CampaignDraft;
  campaign: Campaign;
}

export interface CampaignDeleteResult {
  deleted: boolean;
  campaign_id: string;
  associated_leads: number;
  leads_deleted: number;
  shared_leads_retained: number;
  outreach_batches_deleted: number;
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

export interface OutreachActivity {
  id: string;
  draft_id: string;
  action:
    | "outreach.draft_generated"
    | "outreach.draft_edited"
    | "outreach.draft_approved"
    | "outreach.draft_rejected"
    | "outreach.draft_reopened"
    | "outreach.zoho_open_clicked"
    | "outreach.zoho_open_failed";
  version: number | null;
  reason: string | null;
  recipient_email: string | null;
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
  contact_first_name: string | null;
  contact_last_name: string | null;
  contact_role: string | null;
  contact_email: string | null;
  contact_source_reference: string | null;
  personalisation_observation: string | null;
  relevance_opportunity: string | null;
  offer_angle: string | null;
  desired_next_step: string | null;
  avoid_mentioning: string | null;
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
  outreach_hold_until: string | null;
  outreach_hold_reason: string | null;
  current_score: number | null;
  score_updated_at: string | null;
  campaign_ids: string[];
  sources: SourceObservation[];
  stage_events: StageEvent[];
  notes: LeadNote[];
  follow_ups: FollowUp[];
  communications: Communication[];
  outreach_activities: OutreachActivity[];
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
  average_draft_edit_ratio: number | null;
  approved_drafts_measured: number;
  pipeline: Record<string, number>;
}

export interface WorkspaceSettings {
  retention_review_days: number;
  follow_up_window_days: number;
  default_campaign_radius_miles: number;
  default_weekly_shortlist_size: number;
  weekly_outreach_global_limit: number;
  local_campaign_assistant_enabled: boolean;
  protect_design_software_resources: boolean;
  local_ai_model: string;
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
  summary: string | null;
  materials: string[];
  occasions: string[];
  product_url: string | null;
  b2b_relevant: boolean;
  bulk_ready: boolean;
  b2b_notes: string | null;
  custom_options: string | null;
  enrichment_source: string;
  stale_enrichment: boolean;
  last_seen_import_at: string | null;
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

export interface OutreachLeadOption {
  id: string;
  business_name: string;
  location: string;
  pipeline_stage: string;
  public_email: string | null;
  contact_classification: string;
  current_score: number | null;
  outreach_hold_until: string | null;
  outreach_hold_reason: string | null;
  ready: boolean;
  blockers: string[];
  warnings: string[];
  latest_notes: string[];
}

export interface OutreachDraftRevision {
  id: string;
  version: number;
  subject: string;
  body: string;
  content_hash: string;
  editor: string;
  created_at: string;
}

export interface OutreachDraft {
  id: string;
  batch_id: string;
  lead_id: string;
  business_name: string;
  location: string;
  pipeline_stage: string;
  recipient_email: string;
  contact_classification: string;
  current_score: number | null;
  outreach_hold_until: string | null;
  outreach_hold_reason: string | null;
  latest_notes: string[];
  template_id: string | null;
  review_status: "pending_review" | "approved" | "rejected";
  sync_status: string;
  current_version: number;
  approved_version: number | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  blocked_reason: string | null;
  current_revision: OutreachDraftRevision;
  revision_count: number;
  created_at: string;
  updated_at: string;
}

export interface OutreachZohoHandoff {
  draft_id: string;
  lead_id: string;
  recipient_email: string;
  subject: string;
  body: string;
  version: number;
  opened_at: string;
}

export interface OutreachBatch {
  id: string;
  campaign_id: string | null;
  template_id: string | null;
  template_topic: string | null;
  status: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  sent_count: number;
  drafts: OutreachDraft[];
  created_at: string;
  updated_at: string;
}

export interface ImportIssue {
  handle: string | null;
  message: string;
}

export interface ShopifyImportResult {
  filename: string;
  rows_read: number;
  products_created: number;
  products_updated: number;
  products_skipped: number;
  products_deactivated: number;
  issues: ImportIssue[];
}

export interface EnrichmentImportResult {
  filename: string;
  products_matched: number;
  products_enriched: number;
  products_unmatched: number;
  notes_created: number;
  notes_updated: number;
  fits_created: number;
  fits_skipped: number;
  products_awaiting_enrichment: number;
  fits_awaiting_confirmation: number;
  issues: ImportIssue[];
}

export interface EnrichmentStatus {
  catalogue_imported_at: string | null;
  catalogue_stale: boolean;
  products_total: number;
  products_enriched: number;
  products_awaiting_enrichment: number;
  products_stale_enrichment: number;
  knowledge_notes: number;
  proven_fits: number;
  fits_awaiting_confirmation: number;
}

export interface EnrichmentRunResult {
  products_considered: number;
  products_enriched: number;
  products_failed: number;
  notes_refreshed: number;
  products_awaiting_enrichment: number;
  issues: ImportIssue[];
}

export interface KnowledgeNote {
  id: string;
  title: string;
  segments: string[];
  product_handles: string[];
  body: string;
  source: string;
  manual: boolean;
  updated_at: string;
}

export interface ProvenFit {
  id: string;
  segment: string;
  product_handles: string[];
  use: string;
  outcome: string;
  client_label: string;
  client_name: string | null;
  share_client_name: boolean;
  status: string;
  created_at: string;
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
  week_start: string | null;
  outreach_batch_id: string | null;
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

export interface OutreachDraftRefineInput {
  subject: string;
  body: string;
  instruction?: string;
}

export interface OutreachDraftRefineResult {
  subject: string;
  body: string;
}

export interface LeadFilterTranslateResult {
  stage: string | null;
  suppressed: boolean | null;
  campaign_id: string | null;
  source_type: string | null;
  keyword: string | null;
}

export interface LeadBriefing {
  summary: string;
  talking_points: string[];
  watch_out_for: string | null;
}

export interface LeadAutofillSuggestion {
  personalisation_observation: string | null;
  relevance_opportunity: string | null;
  offer_angle: string | null;
  desired_next_step: string | null;
}

export interface LeadAutofillResultItem {
  lead_id: string;
  business_name: string;
  suggestion: LeadAutofillSuggestion | null;
  skipped_reason: string | null;
}

export interface LeadAutofillResponse {
  items: LeadAutofillResultItem[];
}

export interface StalledLeadSuggestion {
  lead_id: string;
  business_name: string;
  days_stale: number;
  suggested_action: string;
}

export interface StalledLeadDigest {
  generated_at: string;
  items: StalledLeadSuggestion[];
}
