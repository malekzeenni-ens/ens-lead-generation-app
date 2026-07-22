import { invoke } from "@tauri-apps/api/core";

import type {
  ApiErrorShape,
  BackupResult,
  AutomationCapabilities,
  Campaign,
  CampaignRun,
  DiscoveryCandidate,
  Diagnostics,
  Lead,
  InstagramProfilePreview,
  MetaAuthorizationStart,
  MetaConnection,
  OperationsSummary,
  Product,
  ProductFamily,
  ScoreRun,
  ScoringProfile,
  ScoringWeights,
  ShopifyImportResult,
  Shortlist,
  Template,
  VerificationResult,
  WorkspaceSettings,
} from "./types";

interface BackendConnection {
  baseUrl: string;
  sessionToken: string;
}

export class ApiError extends Error {
  constructor(public readonly details: ApiErrorShape) {
    super(details.message);
  }
}

let connectionPromise: Promise<BackendConnection> | undefined;

async function resolveConnection(): Promise<BackendConnection> {
  if (window.__TAURI_INTERNALS__) {
    return invoke<BackendConnection>("backend_connection");
  }
  const baseUrl = import.meta.env.VITE_ENS_API_URL;
  const sessionToken = import.meta.env.VITE_ENS_SESSION_TOKEN;
  if (!baseUrl || !sessionToken) {
    throw new Error(
      "The desktop backend is not connected. Start the app with Start Etch N Shine.cmd instead of opening the Vite URL directly.",
    );
  }
  return { baseUrl, sessionToken };
}

async function rawRequest(path: string, init?: RequestInit): Promise<Response> {
  connectionPromise ??= resolveConnection();
  const connection = await connectionPromise;
  const response = await fetch(`${connection.baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": connection.sessionToken,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const error = (await response.json()) as ApiErrorShape;
    throw new ApiError(error);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await rawRequest(path, init);
  return (await response.json()) as T;
}

function jsonBody(method: string, data: unknown): RequestInit {
  return { method, body: JSON.stringify(data) };
}

export interface CampaignInput {
  name: string;
  description?: string;
  segment: string;
  primary_location: string;
  radius_miles: number;
  keywords: string[];
  exclusion_keywords: string[];
  product_categories: string[];
  product_family_id?: string | null;
  discovery_sources: string[];
  weekly_shortlist_size: number;
  minimum_score_threshold: number;
  preferred_channels: string[];
  offer_settings: Record<string, boolean>;
  discovery_mode: "manual" | "scheduled" | "combined";
}

export interface CampaignUpdate {
  name?: string;
  description?: string | null;
  segment?: string;
  primary_location?: string;
  radius_miles?: number;
  keywords?: string[];
  exclusion_keywords?: string[];
  product_categories?: string[];
  product_family_id?: string | null;
  discovery_sources?: string[];
  weekly_shortlist_size?: number;
  minimum_score_threshold?: number;
  discovery_mode?: "manual" | "scheduled" | "combined";
  status?: "active" | "paused" | "inactive";
}

export interface LeadInput {
  campaign_id: string;
  business_name: string;
  segment: string;
  location: string;
  website?: string;
  social_profile?: string;
  instagram_url?: string;
  facebook_url?: string;
  phone_number?: string;
  public_email?: string;
  contact_classification: string;
  source: {
    name: string;
    source_type: string;
    source_url?: string;
    classification: string;
  };
}

export interface LeadUpdate {
  business_name?: string;
  segment?: string;
  location?: string;
  website?: string | null;
  social_profile?: string | null;
  instagram_url?: string | null;
  facebook_url?: string | null;
  phone_number?: string | null;
  public_email?: string | null;
  contact_classification?: string;
  estimated_order_value?: number | null;
  quote_value?: number | null;
  won_value?: number | null;
  potential_recurrence?: string | null;
  lost_reason?: string | null;
  mock_up_status?: string;
  sample_status?: string;
  quote_status?: string;
  retention_review_date?: string | null;
}

export interface SocialCandidateInput {
  campaign_id: string;
  platform: "instagram" | "facebook";
  profile_url: string;
  business_name: string;
  location: string;
  website?: string;
  phone_number?: string;
  public_email?: string;
  public_bio?: string;
}

export interface ProductInput {
  name: string;
  category: string;
  description?: string;
  target_segments: string[];
  example_use_cases: string[];
  image_reference?: string | null;
  active: boolean;
  pricing_guidance?: string | null;
  sample_eligible: boolean;
}

export type ProductUpdate = Partial<ProductInput>;
export type CampaignRunProvider =
  | "scoring"
  | "google_places"
  | "instagram"
  | "public_registries";

export interface ProductFamilyInput {
  name: string;
  description?: string | null;
  product_ids: string[];
}

export type ProductFamilyUpdate = Partial<ProductFamilyInput>;

export interface TemplateInput {
  topic: string;
  subject?: string;
  body: string;
  product_family_ids?: string[];
}

export type TemplateUpdate = Partial<TemplateInput>;

export interface DownloadResult {
  blob: Blob;
  filename: string;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  campaigns: () => request<Campaign[]>("/campaigns"),
  createCampaign: (data: CampaignInput) =>
    request<Campaign>("/campaigns", jsonBody("POST", data)),
  updateCampaign: (campaignId: string, data: CampaignUpdate) =>
    request<Campaign>(`/campaigns/${campaignId}`, jsonBody("PATCH", data)),
  duplicateCampaign: (campaignId: string, name: string) =>
    request<Campaign>(`/campaigns/${campaignId}/duplicate`, jsonBody("POST", { name })),
  automationCapabilities: () =>
    request<AutomationCapabilities>("/campaign-runs/capabilities"),
  campaignRuns: () => request<CampaignRun[]>("/campaign-runs"),
  startCampaignRun: (campaignId: string, provider: CampaignRunProvider) =>
    request<CampaignRun>(
      "/campaign-runs",
      jsonBody("POST", { campaign_id: campaignId, provider }),
    ),
  startAllCampaignRuns: (provider: CampaignRunProvider) =>
    request<CampaignRun[]>("/campaign-runs/all", jsonBody("POST", { provider })),
  captureSocialCandidate: (data: SocialCandidateInput) =>
    request<CampaignRun>("/social-candidates", jsonBody("POST", data)),
  previewInstagramProfile: (profileUrl: string) =>
    request<InstagramProfilePreview>(
      "/instagram/profiles/preview",
      jsonBody("POST", { profile_url: profileUrl }),
    ),
  importInstagramProfile: (campaignId: string, profileUrl: string) =>
    request<CampaignRun>(
      "/instagram/profiles/import",
      jsonBody("POST", { campaign_id: campaignId, profile_url: profileUrl }),
    ),
  enrichKnownInstagramProfiles: (campaignId: string) =>
    request<CampaignRun>(
      "/instagram/profiles/enrich-known",
      jsonBody("POST", { campaign_id: campaignId }),
    ),
  cancelCampaignRun: (runId: string) =>
    request<CampaignRun>(`/campaign-runs/${runId}/cancel`, jsonBody("POST", {})),
  decideDiscoveryCandidate: (
    candidateId: string,
    action: "promote" | "link" | "reject",
    leadId?: string,
    reason?: string,
  ) =>
    request<DiscoveryCandidate>(
      `/discovery-candidates/${candidateId}/decision`,
      jsonBody("POST", { action, lead_id: leadId ?? null, reason: reason ?? null }),
    ),
  leads: () => request<Lead[]>("/leads"),
  createLead: (data: LeadInput) => request<Lead>("/leads", jsonBody("POST", data)),
  updateLead: (leadId: string, data: LeadUpdate) =>
    request<Lead>(`/leads/${leadId}`, jsonBody("PATCH", data)),
  changeLeadStage: (leadId: string, stage: string, reason?: string) =>
    request<Lead>(`/leads/${leadId}/stage`, jsonBody("POST", { stage, reason })),
  addLeadNote: (leadId: string, content: string) =>
    request<Lead>(`/leads/${leadId}/notes`, jsonBody("POST", { content })),
  addFollowUp: (leadId: string, data: Record<string, unknown>) =>
    request<Lead>(`/leads/${leadId}/follow-ups`, jsonBody("POST", data)),
  completeFollowUp: (leadId: string, followUpId: string) =>
    request<Lead>(
      `/leads/${leadId}/follow-ups/${followUpId}/complete`,
      jsonBody("POST", { next_follow_up: null }),
    ),
  addCommunication: (leadId: string, data: Record<string, unknown>) =>
    request<Lead>(`/leads/${leadId}/communications`, jsonBody("POST", data)),
  suppressLead: (leadId: string, data: Record<string, unknown>) =>
    request<Lead>(`/leads/${leadId}/suppression`, jsonBody("POST", data)),
  liftSuppression: (leadId: string) =>
    request<Lead>(`/leads/${leadId}/suppression`, { method: "DELETE" }),
  deleteLead: (leadId: string) =>
    request<{ deleted: boolean; suppression_evidence_retained: boolean }>(`/leads/${leadId}`, {
      method: "DELETE",
    }),
  products: () => request<Product[]>("/catalogue/products"),
  createProduct: (data: ProductInput) =>
    request<Product>("/catalogue/products", jsonBody("POST", data)),
  updateProduct: (productId: string, data: ProductUpdate) =>
    request<Product>(`/catalogue/products/${productId}`, jsonBody("PATCH", data)),
  importShopifyCsv: (filename: string, content: string) =>
    request<ShopifyImportResult>(
      "/catalogue/import/shopify",
      jsonBody("POST", { filename, content }),
    ),
  productFamilies: () => request<ProductFamily[]>("/catalogue/product-families"),
  createProductFamily: (data: ProductFamilyInput) =>
    request<ProductFamily>("/catalogue/product-families", jsonBody("POST", data)),
  updateProductFamily: (familyId: string, data: ProductFamilyUpdate) =>
    request<ProductFamily>(`/catalogue/product-families/${familyId}`, jsonBody("PATCH", data)),
  deleteProductFamily: (familyId: string) =>
    rawRequest(`/catalogue/product-families/${familyId}`, { method: "DELETE" }).then(
      () => undefined,
    ),
  scoringProfile: (segment: string) =>
    request<ScoringProfile>(`/scoring/profiles/${encodeURIComponent(segment)}`),
  updateScoringProfile: (segment: string, name: string, weights: ScoringWeights) =>
    request<ScoringProfile>(
      `/scoring/profiles/${encodeURIComponent(segment)}`,
      jsonBody("PATCH", { name, weights }),
    ),
  latestScores: () => request<ScoreRun[]>("/scores/latest"),
  calculateScore: (leadId: string, campaignId: string) =>
    request<ScoreRun>(`/leads/${leadId}/score`, jsonBody("POST", { campaign_id: campaignId })),
  overrideScore: (leadId: string, finalScore: number, reason: string) =>
    request<ScoreRun>(
      `/leads/${leadId}/score/override`,
      jsonBody("POST", { final_score: finalScore, reason }),
    ),
  shortlists: () => request<Shortlist[]>("/shortlists"),
  generateShortlist: (campaignId: string, weekStart: string, size: number) =>
    request<Shortlist>(
      "/shortlists/generate",
      jsonBody("POST", { campaign_id: campaignId, week_start: weekStart, size }),
    ),
  shortlistAction: (shortlistId: string, itemId: string, action: string, reason?: string) =>
    request<Shortlist>(
      `/shortlists/${shortlistId}/items/${itemId}/action`,
      jsonBody("POST", { action, reason: reason || null }),
    ),
  summary: () => request<OperationsSummary>("/system/summary"),
  settings: () => request<WorkspaceSettings>("/system/settings"),
  updateSettings: (data: Partial<WorkspaceSettings>) =>
    request<WorkspaceSettings>("/system/settings", jsonBody("PATCH", data)),
  diagnostics: () => request<Diagnostics>("/system/diagnostics"),
  metaConnection: () => request<MetaConnection>("/system/providers/meta"),
  configureMeta: (appId: string, appSecret: string) =>
    request<MetaConnection>(
      "/system/providers/meta",
      jsonBody("PUT", { app_id: appId, app_secret: appSecret }),
    ),
  startMetaAuthorization: () =>
    request<MetaAuthorizationStart>(
      "/system/providers/meta/authorize",
      jsonBody("POST", {}),
    ),
  selectMetaAccount: (pageId: string) =>
    request<MetaConnection>(
      "/system/providers/meta/account",
      jsonBody("POST", { page_id: pageId }),
    ),
  disconnectMeta: () =>
    request<MetaConnection>(
      "/system/providers/meta/disconnect",
      jsonBody("POST", {}),
    ),
  removeMetaConfiguration: () =>
    request<MetaConnection>("/system/providers/meta", { method: "DELETE" }),
  createBackup: (targetDirectory: string) =>
    request<BackupResult>("/backups", jsonBody("POST", { target_directory: targetDirectory })),
  verifyBackup: (backupPath: string) =>
    request<VerificationResult>("/backups/verify", jsonBody("POST", { backup_path: backupPath })),
  exportLeads: async (format: "csv" | "json"): Promise<DownloadResult> => {
    const response = await rawRequest(`/leads/export?format=${format}`);
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = /filename="([^"]+)"/.exec(disposition);
    return {
      blob: await response.blob(),
      filename: match?.[1] ?? `etch-n-shine-leads.${format}`,
    };
  },
  templates: () => request<Template[]>("/templates"),
  createTemplate: (data: TemplateInput) =>
    request<Template>("/templates", jsonBody("POST", data)),
  updateTemplate: (templateId: string, data: TemplateUpdate) =>
    request<Template>(`/templates/${templateId}`, jsonBody("PATCH", data)),
  deleteTemplate: (templateId: string) =>
    rawRequest(`/templates/${templateId}`, { method: "DELETE" }).then(() => undefined),
};
