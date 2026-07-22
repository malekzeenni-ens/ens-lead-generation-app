import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { openUrl } from "@tauri-apps/plugin-opener";

import App from "./App";
import { api, ApiError } from "./api";
import type {
  ApiErrorShape,
  AutomationCapabilities,
  Campaign,
  CampaignRun,
  Diagnostics,
  InstagramProfilePreview,
  Lead,
  MetaConnection,
  OperationsSummary,
  Product,
  ProductFamily,
  ScoreRun,
  ScoringProfile,
  ShopifyImportResult,
  Shortlist,
  Template,
  WorkspaceSettings,
} from "./types";

vi.mock("./api", () => {
  class MockApiError extends Error {
    details: ApiErrorShape;
    constructor(details: ApiErrorShape) {
      super(details.message);
      this.details = details;
    }
  }
  return {
    ApiError: MockApiError,
    api: {
      health: vi.fn(),
      campaigns: vi.fn(),
      leads: vi.fn(),
      summary: vi.fn(),
      settings: vi.fn(),
      diagnostics: vi.fn(),
      products: vi.fn(),
      latestScores: vi.fn(),
      shortlists: vi.fn(),
      scoringProfile: vi.fn(),
      createCampaign: vi.fn(),
      updateCampaign: vi.fn(),
      duplicateCampaign: vi.fn(),
      automationCapabilities: vi.fn(),
      campaignRuns: vi.fn(),
      startCampaignRun: vi.fn(),
      startAllCampaignRuns: vi.fn(),
      captureSocialCandidate: vi.fn(),
      previewInstagramProfile: vi.fn(),
      importInstagramProfile: vi.fn(),
      enrichKnownInstagramProfiles: vi.fn(),
      cancelCampaignRun: vi.fn(),
      decideDiscoveryCandidate: vi.fn(),
      createLead: vi.fn(),
      updateLead: vi.fn(),
      changeLeadStage: vi.fn(),
      addLeadNote: vi.fn(),
      addFollowUp: vi.fn(),
      completeFollowUp: vi.fn(),
      addCommunication: vi.fn(),
      suppressLead: vi.fn(),
      liftSuppression: vi.fn(),
      deleteLead: vi.fn(),
      createProduct: vi.fn(),
      updateProduct: vi.fn(),
      importShopifyCsv: vi.fn(),
      updateScoringProfile: vi.fn(),
      calculateScore: vi.fn(),
      overrideScore: vi.fn(),
      generateShortlist: vi.fn(),
      shortlistAction: vi.fn(),
      updateSettings: vi.fn(),
      exportLeads: vi.fn(),
      createBackup: vi.fn(),
      verifyBackup: vi.fn(),
      metaConnection: vi.fn(),
      configureMeta: vi.fn(),
      startMetaAuthorization: vi.fn(),
      selectMetaAccount: vi.fn(),
      disconnectMeta: vi.fn(),
      removeMetaConfiguration: vi.fn(),
      templates: vi.fn(),
      createTemplate: vi.fn(),
      updateTemplate: vi.fn(),
      deleteTemplate: vi.fn(),
      productFamilies: vi.fn(),
      createProductFamily: vi.fn(),
      updateProductFamily: vi.fn(),
      deleteProductFamily: vi.fn(),
    },
  };
});

vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: vi.fn() }));

const campaign: Campaign = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Luton Bakery Partnerships",
  description: null,
  segment: "Bakeries and home bakers",
  primary_location: "Luton, United Kingdom",
  radius_miles: 25,
  keywords: [],
  exclusion_keywords: [],
  product_categories: ["Cake toppers"],
  product_family_id: null,
  discovery_sources: ["manual"],
  weekly_shortlist_size: 5,
  minimum_score_threshold: 0,
  preferred_channels: ["email", "instagram"],
  offer_settings: { digital_mock_up: true },
  discovery_mode: "manual",
  status: "active",
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};

const lead: Lead = {
  id: "22222222-2222-2222-2222-222222222222",
  business_name: "Example Celebration Cakes",
  segment: "Bakeries and home bakers",
  location: "Luton",
  website: "https://example.test",
  social_profile: null,
  phone_number: null,
  public_email: null,
  social_identities: [],
  contact_classification: "unknown",
  pipeline_stage: "new",
  suppressed: false,
  estimated_order_value: null,
  quote_value: null,
  won_value: null,
  potential_recurrence: null,
  lost_reason: null,
  mock_up_status: "not_offered",
  sample_status: "not_applicable",
  quote_status: "not_requested",
  retention_review_date: null,
  current_score: null,
  score_updated_at: null,
  campaign_ids: [campaign.id],
  sources: [
    {
      id: "33333333-3333-3333-3333-333333333333",
      source_name: "Manual entry",
      source_type: "manual",
      field_name: "business_identity",
      observed_value: "Example Celebration Cakes",
      classification: "user_verified",
      source_url: "https://example.test",
      collection_method: "manual_entry",
      collected_at: "2026-07-18T10:00:00Z",
    },
  ],
  stage_events: [
    {
      id: "44444444-4444-4444-4444-444444444444",
      previous_stage: null,
      new_stage: "new",
      actor: "local_user",
      reason: "Manual lead entry",
      created_at: "2026-07-18T10:00:00Z",
    },
  ],
  notes: [],
  follow_ups: [],
  communications: [],
  suppression_records: [],
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};

const summary: OperationsSummary = {
  campaigns: 1,
  active_campaigns: 1,
  leads: 1,
  suppressed_leads: 0,
  review_required: 1,
  open_follow_ups: 0,
  due_today: 0,
  overdue: 0,
  due_this_week: 0,
  products: 1,
  scored_leads: 1,
  shortlisted_this_week: 1,
  pipeline: { new: 1 },
};

const settings: WorkspaceSettings = {
  retention_review_days: 365,
  follow_up_window_days: 7,
  default_campaign_radius_miles: 25,
  default_weekly_shortlist_size: 5,
};

const diagnostics: Diagnostics = {
  api_status: "ok",
  database_status: "connected",
  schema_version: "0005_contact_social",
  database_size_bytes: 131_072,
  journal_mode: "wal",
  foreign_keys_enabled: true,
  data_directory: "C:\\LocalData",
  log_directory: "C:\\LocalData\\logs",
  campaigns: 1,
  leads: 1,
  audit_events: 2,
  backups: 0,
  products: 1,
  score_runs: 1,
  shortlists: 1,
  campaign_runs: 0,
  discovery_candidates: 0,
  provider_mode: "disabled",
  outbound_messaging: "disabled",
};

const product: Product = {
  id: "55555555-5555-5555-5555-555555555555",
  shopify_handle: "personalised-cake-topper",
  name: "Personalised Cake Topper",
  category: "Cake toppers",
  description: "Mirror acrylic topper",
  target_segments: [campaign.segment],
  example_use_cases: ["Celebration cakes"],
  image_reference: null,
  active: true,
  pricing_guidance: "£12.50",
  sample_eligible: true,
  source: "shopify_csv",
  variant_count: 1,
  created_at: "2026-07-19T10:00:00Z",
  updated_at: "2026-07-19T10:00:00Z",
};

const template: Template = {
  id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
  topic: "Follow-up",
  subject: "Following up, {{business_name}}",
  body: "Hi {{business_name}}, checking in about your order.",
  product_family_ids: [],
  created_at: "2026-07-19T10:00:00Z",
  updated_at: "2026-07-19T10:00:00Z",
};

const productFamily: ProductFamily = {
  id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
  name: "Cake celebration range",
  description: "Everything for a celebration cake order.",
  products: [product],
  created_at: "2026-07-19T10:00:00Z",
  updated_at: "2026-07-19T10:00:00Z",
};

const scoringProfile: ScoringProfile = {
  id: "66666666-6666-6666-6666-666666666666",
  name: "Bakery deterministic model",
  segment: campaign.segment,
  version: 1,
  weights: {
    business_relevance: 25,
    activity: 20,
    product_fit: 20,
    local_relevance: 15,
    commercial_potential: 10,
    reach_credibility: 5,
    contactability: 5,
  },
  active: true,
  created_at: "2026-07-19T10:00:00Z",
};

const scoreRun: ScoreRun = {
  id: "77777777-7777-7777-7777-777777777777",
  lead_id: lead.id,
  campaign_id: campaign.id,
  profile_id: scoringProfile.id,
  profile_name: scoringProfile.name,
  profile_version: 1,
  rule_version: "deterministic-local-v1",
  campaign_run_id: null,
  input_fingerprint: null,
  calculated_score: 72,
  final_score: 72,
  manual_override: false,
  override_reason: null,
  breakdown: [
    {
      category: "Business relevance",
      points_awarded: 20,
      points_available: 25,
      evidence_used: ["lead.segment:bakery"],
      missing_evidence: ["Personalised or event-work evidence"],
      ai_inference: null,
    },
  ],
  product_matches: [
    {
      product_id: product.id,
      product_name: product.name,
      category: product.category,
      match_score: 100,
      reason: "Target segment and campaign category match.",
      evidence: ["lead.segment:Bakeries and home bakers"],
      rule_based: true,
    },
  ],
  created_at: "2026-07-19T10:00:00Z",
  overridden_at: null,
};

const automationCapabilities: AutomationCapabilities = {
  google_places_configured: true,
  instagram_configured: false,
  instagram_connected: false,
  instagram_account: null,
  instagram_status: "not_configured",
  website_enrichment_enabled: true,
  public_registries_available: true,
  maximum_results_per_campaign: 40,
  maximum_queries_per_campaign: 3,
  outbound_messaging: "disabled",
};

const metaConnection: MetaConnection = {
  configured: false,
  connected: false,
  status: "not_configured",
  callback_url: "http://localhost:8766/meta/oauth/callback",
  graph_version: "v25.0",
  accounts: [],
  selected_account: null,
  expires_at: null,
  error_message: null,
};

const instagramProfilePreview: InstagramProfilePreview = {
  account_id: "business-42",
  username: "donmillersuk",
  profile_url: "https://www.instagram.com/donmillersuk",
  business_name: "Don Millers",
  biography: "Luton bakery. Email hello@donmillers.example",
  website: "https://donmillers.example",
  public_email: "hello@donmillers.example",
  public_phone: "+44 1582 111222",
  followers_count: 850,
  media_count: 95,
};

const campaignRun: CampaignRun = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  batch_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  campaign_id: campaign.id,
  campaign_name: campaign.name,
  trigger: "manual",
  status: "completed_with_warnings",
  phase: "completed",
  provider_status: "not_requested",
  query_summary: null,
  metrics: {
    discovered: 0,
    promoted: 0,
    leads_scored: 1,
    scores_unchanged: 0,
    qualified: 1,
    shortlist_selected: 1,
  },
  warnings: ["This campaign uses existing leads only; Google Places is not selected."],
  error_code: null,
  error_message: null,
  cancellation_requested: false,
  created_at: "2026-07-19T10:00:00Z",
  started_at: "2026-07-19T10:00:00Z",
  completed_at: "2026-07-19T10:00:01Z",
  updated_at: "2026-07-19T10:00:01Z",
  candidates: [],
  attempts: [],
};

const shortlist: Shortlist = {
  id: "88888888-8888-8888-8888-888888888888",
  campaign_id: campaign.id,
  campaign_name: campaign.name,
  week_start: "2026-07-20",
  capacity: 5,
  status: "active",
  items: [
    {
      id: "99999999-9999-9999-9999-999999999999",
      lead_id: lead.id,
      business_name: lead.business_name,
      segment: lead.segment,
      location: lead.location,
      pipeline_stage: "recommended_this_week",
      score: 72,
      rank: 1,
      decision: "recommended",
      reason: "Score 72/100; public contact route; matched Personalised Cake Topper.",
      product_matches: scoreRun.product_matches,
      created_at: "2026-07-19T10:00:00Z",
      decided_at: null,
    },
  ],
  created_at: "2026-07-19T10:00:00Z",
  updated_at: "2026-07-19T10:00:00Z",
};

const importResult: ShopifyImportResult = {
  filename: "products_export.csv",
  rows_read: 2,
  products_created: 1,
  products_updated: 0,
  products_skipped: 0,
  issues: [],
};

describe("local operating workbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.health).mockResolvedValue({ status: "ok" });
    vi.mocked(api.campaigns).mockResolvedValue([campaign]);
    vi.mocked(api.leads).mockResolvedValue([lead]);
    vi.mocked(api.summary).mockResolvedValue(summary);
    vi.mocked(api.settings).mockResolvedValue(settings);
    vi.mocked(api.diagnostics).mockResolvedValue(diagnostics);
    vi.mocked(api.products).mockResolvedValue([product]);
    vi.mocked(api.latestScores).mockResolvedValue([scoreRun]);
    vi.mocked(api.shortlists).mockResolvedValue([shortlist]);
    vi.mocked(api.scoringProfile).mockResolvedValue(scoringProfile);
    vi.mocked(api.createCampaign).mockResolvedValue(campaign);
    vi.mocked(api.updateCampaign).mockResolvedValue(campaign);
    vi.mocked(api.duplicateCampaign).mockResolvedValue(campaign);
    vi.mocked(api.automationCapabilities).mockResolvedValue(automationCapabilities);
    vi.mocked(api.metaConnection).mockResolvedValue(metaConnection);
    vi.mocked(api.campaignRuns).mockResolvedValue([]);
    vi.mocked(api.startCampaignRun).mockResolvedValue(campaignRun);
    vi.mocked(api.startAllCampaignRuns).mockResolvedValue([campaignRun]);
    vi.mocked(api.captureSocialCandidate).mockResolvedValue(campaignRun);
    vi.mocked(api.previewInstagramProfile).mockResolvedValue(instagramProfilePreview);
    vi.mocked(api.importInstagramProfile).mockResolvedValue(campaignRun);
    vi.mocked(api.enrichKnownInstagramProfiles).mockResolvedValue(campaignRun);
    vi.mocked(api.createLead).mockResolvedValue(lead);
    vi.mocked(api.updateLead).mockResolvedValue(lead);
    vi.mocked(api.changeLeadStage).mockResolvedValue({ ...lead, pipeline_stage: "qualified" });
    vi.mocked(api.addLeadNote).mockResolvedValue(lead);
    vi.mocked(api.addFollowUp).mockResolvedValue(lead);
    vi.mocked(api.completeFollowUp).mockResolvedValue(lead);
    vi.mocked(api.addCommunication).mockResolvedValue(lead);
    vi.mocked(api.suppressLead).mockResolvedValue({ ...lead, suppressed: true });
    vi.mocked(api.liftSuppression).mockResolvedValue(lead);
    vi.mocked(api.deleteLead).mockResolvedValue({
      deleted: true,
      suppression_evidence_retained: false,
    });
    vi.mocked(api.createProduct).mockResolvedValue(product);
    vi.mocked(api.updateProduct).mockResolvedValue(product);
    vi.mocked(api.importShopifyCsv).mockResolvedValue(importResult);
    vi.mocked(api.updateScoringProfile).mockResolvedValue(scoringProfile);
    vi.mocked(api.calculateScore).mockResolvedValue(scoreRun);
    vi.mocked(api.overrideScore).mockResolvedValue(scoreRun);
    vi.mocked(api.generateShortlist).mockResolvedValue(shortlist);
    vi.mocked(api.shortlistAction).mockResolvedValue(shortlist);
    vi.mocked(api.updateSettings).mockResolvedValue(settings);
    vi.mocked(api.configureMeta).mockResolvedValue({
      ...metaConnection,
      configured: true,
      status: "configured",
    });
    vi.mocked(api.disconnectMeta).mockResolvedValue(metaConnection);
    vi.mocked(api.removeMetaConfiguration).mockResolvedValue(metaConnection);
    vi.mocked(api.templates).mockResolvedValue([template]);
    vi.mocked(api.createTemplate).mockResolvedValue(template);
    vi.mocked(api.updateTemplate).mockResolvedValue(template);
    vi.mocked(api.deleteTemplate).mockResolvedValue(undefined);
    vi.mocked(api.productFamilies).mockResolvedValue([productFamily]);
    vi.mocked(api.createProductFamily).mockResolvedValue(productFamily);
    vi.mocked(api.updateProductFamily).mockResolvedValue(productFamily);
    vi.mocked(api.deleteProductFamily).mockResolvedValue(undefined);
  });

  it("shows the accessible desktop shell and operating summary", async () => {
    render(<App />);
    expect(await screen.findByText("API connected")).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Workspace navigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "location",
    );
    expect(screen.getByRole("heading", { name: "Lead intelligence dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Controlled mode")).toBeInTheDocument();
    expect(screen.getByText("Active campaigns")).toBeInTheDocument();
  });

  it("navigates from a dashboard metric card to the pre-filtered leads register", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");

    await user.click(screen.getByRole("button", { name: /Needs review/ }));

    expect(screen.getByRole("heading", { name: "All leads" })).toBeInTheDocument();
    expect(
      within(screen.getByRole("combobox", { name: "Filter by review status" })),
    ).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Filter by review status" })).toHaveValue(
      "review",
    );
    expect(screen.getByText(lead.business_name)).toBeInTheDocument();
  });

  it("navigates from the Active products card straight to the Catalogue workspace", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");

    await user.click(screen.getByRole("button", { name: /Active products/ }));

    expect(screen.getByRole("heading", { name: "Catalogue and scoring" })).toBeInTheDocument();
  });

  it("creates a product family in Catalogue and assigns it to a campaign", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");

    await user.click(screen.getByRole("link", { name: /Catalogue/ }));
    await user.click(screen.getByRole("tab", { name: /Product families/ }));
    expect(screen.getByRole("heading", { name: "Cake celebration range" })).toBeInTheDocument();

    await user.type(
      screen.getByRole("textbox", { name: "Family name" }),
      "Gym signage range",
    );
    await user.click(
      screen.getAllByRole("checkbox", { name: /Personalised Cake Topper/ })[0]!,
    );
    await user.click(screen.getByRole("button", { name: "Create product family" }));
    await waitFor(() =>
      expect(api.createProductFamily).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Gym signage range", product_ids: [product.id] }),
      ),
    );

    await user.click(screen.getByRole("link", { name: /Campaigns/ }));
    await user.click(screen.getByRole("tab", { name: "Create campaign" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: /Product family/ }),
      productFamily.id,
    );
    await user.type(
      screen.getByRole("textbox", { name: "Campaign name" }),
      "Family assigned campaign",
    );
    await user.click(screen.getByRole("button", { name: "Create campaign" }));
    await waitFor(() =>
      expect(api.createCampaign).toHaveBeenCalledWith(
        expect.objectContaining({ product_family_id: productFamily.id }),
      ),
    );
  });

  it("keeps a product family's existing products when searching for and adding another one", async () => {
    const user = userEvent.setup();
    const secondProduct = {
      ...product,
      id: "66666666-aaaa-bbbb-cccc-666666666666",
      shopify_handle: "engraved-bottle-opener",
      name: "Engraved Bottle Opener",
      category: "Barware",
    };
    vi.mocked(api.products).mockResolvedValue([product, secondProduct]);

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Catalogue/ }));
    await user.click(screen.getByRole("tab", { name: /Product families/ }));
    await user.click(screen.getByText("Edit family"));

    const editForm = screen.getByRole("button", { name: "Save family" }).closest("form");
    if (!editForm) throw new Error("Edit family form is missing.");

    // The family's existing product (Personalised Cake Topper) does not match this search,
    // but its checkbox must stay checked and still be submitted once it's hidden.
    await user.type(within(editForm).getByPlaceholderText("Search products to add"), "bottle");
    await user.click(within(editForm).getByRole("checkbox", { name: /Engraved Bottle Opener/ }));
    await user.click(within(editForm).getByRole("button", { name: "Save family" }));

    await waitFor(() =>
      expect(api.updateProductFamily).toHaveBeenCalledWith(productFamily.id, {
        name: productFamily.name,
        description: productFamily.description,
        product_ids: [product.id, secondProduct.id],
      }),
    );
  });

  it("shows the error banner and marks the API unavailable when the initial health check fails", async () => {
    vi.mocked(api.health).mockRejectedValue(new Error("Simulated backend outage"));

    render(<App />);

    expect(await screen.findByText("API unavailable")).toBeInTheDocument();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Action could not be completed");
    expect(alert).toHaveTextContent("Simulated backend outage");
  });

  it("surfaces field-level validation details in the error banner", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createCampaign).mockRejectedValue(
      new ApiError({
        code: "VALIDATION_ERROR",
        message: "The request contains invalid or missing values.",
        details: {
          errors: [
            { location: ["body", "radius_miles"], message: "Input should be greater than 0", type: "greater_than" },
          ],
        },
        correlation_id: "corr-999",
      }),
    );

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));
    await user.click(screen.getByRole("tab", { name: "Create campaign" }));
    await user.type(screen.getByRole("textbox", { name: "Campaign name" }), "New Luton Campaign");
    await user.click(screen.getByRole("button", { name: "Create campaign" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("radius_miles: Input should be greater than 0");
  });

  it("switches task tabs with the keyboard", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));

    const campaignsTab = screen.getByRole("tab", { name: /Campaigns/ });
    campaignsTab.focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Create campaign" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("textbox", { name: "Campaign name" })).toBeInTheDocument();
  });

  it("creates a configured campaign from the campaign workspace", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));
    await user.click(screen.getByRole("tab", { name: "Create campaign" }));
    const name = screen.getByRole("textbox", { name: "Campaign name" });
    await user.type(name, "New Luton Campaign");
    const minimumScore = screen.getByRole("spinbutton", { name: "Minimum shortlist score" });
    await user.clear(minimumScore);
    await user.type(minimumScore, "65");
    const productCategories = screen.getByRole("textbox", { name: "Product categories" });
    await user.clear(productCategories);
    await user.type(productCategories, "Cake toppers, Wedding signage, cake toppers");
    await user.click(screen.getByRole("button", { name: "Create campaign" }));
    await waitFor(() => expect(api.createCampaign).toHaveBeenCalledTimes(1));
    expect(api.createCampaign).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "New Luton Campaign",
        primary_location: "Luton, United Kingdom",
        radius_miles: 25,
        weekly_shortlist_size: 5,
        minimum_score_threshold: 65,
        product_categories: ["Cake toppers", "Wedding signage"],
      }),
    );
    expect(await screen.findByText("Campaign created and stored locally.")).toBeInTheDocument();
  });

  it("runs scoring and product matching for a campaign on demand", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));

    await user.click(screen.getByRole("button", { name: "Refresh scoring only" }));

    await waitFor(() =>
      expect(api.startCampaignRun).toHaveBeenCalledWith(campaign.id, "scoring"),
    );
    expect(
      await screen.findByText(
        "Scoring run started. Only the selected discovery source will run before scoring and shortlist preparation.",
      ),
    ).toBeInTheDocument();
  });

  it("runs Google Places and Instagram as separate campaign actions", async () => {
    const user = userEvent.setup();
    const providerCampaign = {
      ...campaign,
      discovery_sources: ["manual", "google_places", "instagram"],
    };
    vi.mocked(api.campaigns).mockResolvedValue([providerCampaign]);
    vi.mocked(api.automationCapabilities).mockResolvedValue({
      ...automationCapabilities,
      instagram_configured: true,
      instagram_connected: true,
      instagram_account: "etchnshine",
      instagram_status: "connected",
    });

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));

    await user.click(screen.getByRole("button", { name: "Run Google Places" }));
    await waitFor(() =>
      expect(api.startCampaignRun).toHaveBeenCalledWith(campaign.id, "google_places"),
    );

    await user.click(screen.getByRole("button", { name: "Refresh Instagram profiles" }));
    await waitFor(() =>
      expect(api.startCampaignRun).toHaveBeenCalledWith(campaign.id, "instagram"),
    );
  });

  it("shows a non-blocking header indicator while a campaign run is active", async () => {
    const user = userEvent.setup();
    vi.mocked(api.campaignRuns)
      .mockResolvedValueOnce([])
      .mockResolvedValue([{ ...campaignRun, status: "queued" }]);

    render(<App />);
    await screen.findByText("API connected");
    expect(screen.queryByText(/Running:/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Campaigns/ }));
    await user.click(screen.getByRole("button", { name: "Refresh scoring only" }));

    expect(await screen.findByText(`Running: ${campaignRun.campaign_name}`)).toBeInTheDocument();
    // Other controls stay usable — this is a status badge, not a blocking overlay.
    expect(screen.getByRole("link", { name: /Templates/ })).not.toHaveAttribute("aria-disabled");
  });

  it("keeps a longer notification visible proportionally longer, then dismisses it", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));

    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Refresh scoring only" }));
        await Promise.resolve();
      });

      const message =
        "Scoring run started. Only the selected discovery source will run before scoring and shortlist preparation.";
      expect(screen.getByText(message)).toBeInTheDocument();

      // 106 characters * 60ms/char = 6,360ms — longer than the 5s floor used for short toasts.
      await act(() => vi.advanceTimersByTime(6_359));
      expect(screen.getByText(message)).toBeInTheDocument();

      await act(() => vi.advanceTimersByTime(1));
      expect(screen.queryByText(message)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });


  it("previews and imports a professional Instagram profile through Meta", async () => {
    const user = userEvent.setup();
    vi.mocked(api.automationCapabilities).mockResolvedValue({
      ...automationCapabilities,
      instagram_configured: true,
      instagram_connected: true,
      instagram_account: "etchnshine",
      instagram_status: "connected",
    });
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));
    await user.click(screen.getByRole("tab", { name: "Social leads" }));

    const panel = screen
      .getByRole("heading", { name: "Import one Instagram profile" })
      .closest<HTMLElement>(".form-panel");
    if (!panel) throw new Error("Instagram import panel is missing.");
    await user.type(
      within(panel).getByRole("textbox", { name: "Instagram profile URL" }),
      "https://www.instagram.com/donmillersuk/",
    );
    await user.click(within(panel).getByRole("button", { name: "Fetch from Meta" }));

    await waitFor(() =>
      expect(api.previewInstagramProfile).toHaveBeenCalledWith(
        "https://www.instagram.com/donmillersuk/",
      ),
    );
    expect(await screen.findByText("Don Millers")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Import, score and match" }));
    await waitFor(() =>
      expect(api.importInstagramProfile).toHaveBeenCalledWith(
        campaign.id,
        "https://www.instagram.com/donmillersuk",
      ),
    );
  });

  it("bulk enriches Instagram profiles already saved against campaign leads", async () => {
    const user = userEvent.setup();
    vi.mocked(api.automationCapabilities).mockResolvedValue({
      ...automationCapabilities,
      instagram_configured: true,
      instagram_connected: true,
      instagram_account: "etchnshine",
      instagram_status: "connected",
    });
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));
    await user.click(screen.getByRole("tab", { name: "Social leads" }));
    await user.click(screen.getByRole("button", { name: "Enrich saved Instagram profiles" }));

    await waitFor(() =>
      expect(api.enrichKnownInstagramProfiles).toHaveBeenCalledWith(campaign.id),
    );
  });

  it("opens assisted social searches in the Windows default browser", async () => {
    const user = userEvent.setup();
    vi.mocked(openUrl).mockResolvedValue(undefined);
    window.__TAURI_INTERNALS__ = {};

    try {
      render(<App />);
      await screen.findByText("API connected");
      await user.click(screen.getByRole("link", { name: /Campaigns/ }));
      await user.click(screen.getByRole("tab", { name: "Social leads" }));
      await user.click(screen.getByRole("tab", { name: "Find profiles" }));
      await user.click(
        screen.getByRole("button", {
          name: "Open Instagram #lutonbakeriesandhomebakers",
        }),
      );

      await waitFor(() =>
        expect(openUrl).toHaveBeenCalledWith(
          "https://www.instagram.com/explore/tags/lutonbakeriesandhomebakers/",
        ),
      );
      await user.click(
        screen.getByRole("button", {
          name: /Search Facebook for Bakeries and home bakers/i,
        }),
      );
      await waitFor(() =>
        expect(openUrl).toHaveBeenLastCalledWith(expect.stringContaining("google.com/search")),
      );
      expect(
        await screen.findByText(
          "Public social search opened in your browser. Review a profile, then capture its details here.",
        ),
      ).toBeInTheDocument();
    } finally {
      delete window.__TAURI_INTERNALS__;
    }
  });

  it("edits campaign shortlist threshold and product categories", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Campaigns/ }));
    const campaignRecord = screen.getByRole("heading", { name: campaign.name }).closest("article");
    if (!campaignRecord) throw new Error("Campaign record is missing.");
    await user.click(within(campaignRecord).getByRole("button", { name: "Edit" }));

    const minimumScore = within(campaignRecord).getByRole("spinbutton", {
      name: "Minimum shortlist score",
    });
    await user.clear(minimumScore);
    await user.type(minimumScore, "70");
    const productCategories = within(campaignRecord).getByRole("textbox", {
      name: "Product categories",
    });
    await user.clear(productCategories);
    await user.type(productCategories, "Cake toppers, Wedding signage, cake toppers");
    await user.click(within(campaignRecord).getByRole("button", { name: "Save campaign" }));

    await waitFor(() =>
      expect(api.updateCampaign).toHaveBeenCalledWith(
        campaign.id,
        expect.objectContaining({
          minimum_score_threshold: 70,
          product_categories: ["Cake toppers", "Wedding signage"],
        }),
      ),
    );
    expect(await screen.findByText("Campaign changes saved with audit history.")).toBeInTheDocument();
  });

  it("submits an evidence-backed lead", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /All leads/ }));
    await user.click(screen.getByRole("tab", { name: "Add lead" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Campaign" }), campaign.id);
    await user.type(screen.getByRole("textbox", { name: "Business name" }), lead.business_name);
    await user.type(screen.getByRole("textbox", { name: "Location" }), lead.location);
    await user.type(screen.getByRole("textbox", { name: /Website/ }), lead.website ?? "");
    await user.click(screen.getByRole("button", { name: "Add lead with source" }));
    await waitFor(() => expect(api.createLead).toHaveBeenCalledTimes(1));
    expect(api.createLead).toHaveBeenCalledWith(
      expect.objectContaining({
        campaign_id: campaign.id,
        business_name: lead.business_name,
        website: lead.website,
        contact_classification: "unknown",
      }),
    );
    expect(await screen.findByText("Lead added with source evidence and audit history.")).toBeInTheDocument();
  });

  it("filters the lead register by campaign and resets its page", async () => {
    const user = userEvent.setup();
    const secondCampaign: Campaign = {
      ...campaign,
      id: "12121212-1212-1212-1212-121212121212",
      name: "Dunstable Bakery Partnerships",
      primary_location: "Dunstable, United Kingdom",
    };
    const firstCampaignLeads = Array.from({ length: 11 }, (_, index) => ({
      ...lead,
      id: `campaign-one-lead-${index + 1}`,
      business_name: `Luton Campaign Lead ${String(index + 1).padStart(2, "0")}`,
    }));
    const secondCampaignLead: Lead = {
      ...lead,
      id: "campaign-two-lead-1",
      business_name: "Dunstable Campaign Lead",
      campaign_ids: [secondCampaign.id],
    };
    vi.mocked(api.campaigns).mockResolvedValue([campaign, secondCampaign]);
    vi.mocked(api.leads).mockResolvedValue([...firstCampaignLeads, secondCampaignLead]);

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /All leads/ }));

    const pagination = await screen.findByRole("navigation", { name: "leads pagination" });
    await user.click(within(pagination).getByRole("button", { name: "Next leads page" }));
    expect(await screen.findByText("Luton Campaign Lead 11")).toBeInTheDocument();

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Filter by campaign" }),
      secondCampaign.id,
    );
    expect(await screen.findByText(secondCampaignLead.business_name)).toBeInTheDocument();
    expect(screen.queryByText("Luton Campaign Lead 11")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "leads pagination" })).not.toBeInTheDocument();
  });

  it("shows and filters leads by their discovery source", async () => {
    const user = userEvent.setup();
    const googleLead: Lead = {
      ...lead,
      id: "google-lead-1",
      business_name: "Google Bakery",
      sources: [
        {
          ...lead.sources[0]!,
          id: "google-source-1",
          source_name: "Google Places",
          source_type: "google",
          collection_method: "google_places_text_search",
        },
      ],
    };
    const instagramLead: Lead = {
      ...lead,
      id: "instagram-lead-1",
      business_name: "Instagram Bakery",
      sources: [
        {
          ...lead.sources[0]!,
          id: "instagram-source-1",
          source_name: "Instagram via official Meta API",
          source_type: "instagram",
          collection_method: "official_meta_business_discovery",
        },
      ],
    };
    vi.mocked(api.leads).mockResolvedValue([lead, googleLead, instagramLead]);

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /All leads/ }));

    expect(await screen.findByText("Google Bakery")).toBeInTheDocument();
    expect(screen.getByText("Instagram Bakery")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Lead source" })).toBeInTheDocument();

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Filter by lead source" }),
      "instagram",
    );
    expect(await screen.findByText("Instagram Bakery")).toBeInTheDocument();
    expect(screen.queryByText("Google Bakery")).not.toBeInTheDocument();
    expect(screen.queryByText(lead.business_name)).not.toBeInTheDocument();
  });

  it("opens a registered lead in the pipeline workspace", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /All leads/ }));
    await user.click(screen.getByRole("button", { name: "Manage" }));
    expect(screen.getByRole("heading", { name: "Pipeline workspace" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: lead.business_name })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Pipeline/ })).toHaveAttribute(
      "aria-current",
      "location",
    );
  });

  it("opens lead details by default in the pipeline overview", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));

    const disclosure = screen.getByText("Lead details and retention").closest("details");
    expect(disclosure).not.toBeNull();
    expect(disclosure).toHaveAttribute("open");
    expect(screen.getByRole("textbox", { name: "Business name" })).toHaveValue(
      lead.business_name,
    );
  });

  it("shows the lead's website as a link that opens in a new browser tab", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));

    const websiteLink = screen.getByRole("link", { name: lead.website ?? "" });
    expect(websiteLink).toHaveAttribute("href", lead.website);
    expect(websiteLink).toHaveAttribute("target", "_blank");
    expect(websiteLink).toHaveAttribute("rel", "noreferrer");
  });

  it("omits the website link when the lead has no website on file", async () => {
    const user = userEvent.setup();
    vi.mocked(api.leads).mockResolvedValue([{ ...lead, website: null }]);
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));

    expect(screen.queryByRole("link", { name: /example\.test/ })).not.toBeInTheDocument();
  });

  it("changes a pipeline stage and records a note", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));
    await user.click(screen.getByRole("tab", { name: "Opportunity" }));
    const stageCard = screen.getByRole("heading", { name: "Pipeline stage" }).closest("section");
    expect(stageCard).not.toBeNull();
    await user.selectOptions(
      within(stageCard as HTMLElement).getByRole("combobox", { name: "Stage" }),
      "qualified",
    );
    await user.type(
      within(stageCard as HTMLElement).getByRole("textbox", { name: /Reason/ }),
      "Verified product fit",
    );
    await user.click(
      within(stageCard as HTMLElement).getByRole("button", { name: "Change stage" }),
    );
    await waitFor(() =>
      expect(api.changeLeadStage).toHaveBeenCalledWith(lead.id, "qualified", "Verified product fit"),
    );
    await user.click(screen.getByRole("tab", { name: /Activity & follow-up/ }));
    const notesCard = screen.getByRole("heading", { name: "Notes" }).closest("section");
    expect(notesCard).not.toBeNull();
    const noteBox = within(notesCard as HTMLElement).getByRole("textbox", { name: "New note" });
    await user.type(noteBox, "Owner prefers email.");
    await user.click(within(notesCard as HTMLElement).getByRole("button", { name: "Add note" }));
    await waitFor(() => expect(api.addLeadNote).toHaveBeenCalledWith(lead.id, "Owner prefers email."));
  });

  it("applies suppression from the lead control panel", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));
    await user.click(screen.getByRole("tab", { name: "Privacy" }));
    const suppressionCard = screen
      .getByRole("heading", { name: "Suppression and privacy" })
      .closest("section");
    expect(suppressionCard).not.toBeNull();
    await user.type(
      within(suppressionCard as HTMLElement).getByRole("textbox", { name: "Reason" }),
      "Business objected",
    );
    await user.click(
      within(suppressionCard as HTMLElement).getByRole("button", { name: "Apply suppression" }),
    );
    await waitFor(() =>
      expect(api.suppressLead).toHaveBeenCalledWith(
        lead.id,
        expect.objectContaining({
          suppression_type: "do_not_contact",
          reason: "Business objected",
          source: "Local user",
        }),
      ),
    );
  });

  it("saves authenticated local workspace settings", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: "Settings" }));
    await user.click(screen.getByRole("tab", { name: "Defaults" }));
    const retention = screen.getByRole("spinbutton", { name: "Retention review interval days" });
    await user.clear(retention);
    await user.type(retention, "730");
    await user.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() =>
      expect(api.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({ retention_review_days: 730 }),
      ),
    );
    expect(await screen.findByText("Workspace settings saved.")).toBeInTheDocument();
  });

  it("stores Meta credentials through the encrypted provider settings flow", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: "Settings" }));
    await user.type(screen.getByRole("textbox", { name: "Meta App ID" }), "1596694465496867");
    await user.type(screen.getByLabelText("Meta App Secret"), "a-secure-meta-app-secret");
    await user.click(screen.getByRole("button", { name: "Save encrypted credentials" }));
    await waitFor(() =>
      expect(api.configureMeta).toHaveBeenCalledWith(
        "1596694465496867",
        "a-secure-meta-app-secret",
      ),
    );
  });

  it("opens Meta authorization in the Windows default browser", async () => {
    const user = userEvent.setup();
    const configuredMeta = { ...metaConnection, configured: true, status: "configured" };
    const connectedMeta = {
      ...configuredMeta,
      connected: true,
      status: "connected",
      selected_account: {
        page_id: "page-1",
        page_name: "Etch 'N' Shine",
        instagram_account_id: "instagram-1",
        instagram_username: "etchnshine",
      },
    };
    const connectedCapabilities = {
      ...automationCapabilities,
      instagram_configured: true,
      instagram_connected: true,
      instagram_account: "etchnshine",
      instagram_status: "connected",
    };
    vi.mocked(api.metaConnection)
      .mockResolvedValueOnce(configuredMeta)
      .mockResolvedValue(connectedMeta);
    vi.mocked(api.automationCapabilities)
      .mockResolvedValueOnce(automationCapabilities)
      .mockResolvedValue(connectedCapabilities);
    vi.mocked(api.startMetaAuthorization).mockResolvedValue({
      authorization_url: "https://www.facebook.com/v25.0/dialog/oauth?client_id=test",
      expires_at: "2026-07-20T19:30:00Z",
    });
    vi.mocked(openUrl).mockResolvedValue(undefined);
    window.__TAURI_INTERNALS__ = {};

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: "Settings" }));
    await user.click(screen.getByRole("button", { name: "Connect Instagram with Meta" }));

    await waitFor(() =>
      expect(openUrl).toHaveBeenCalledWith(
        "https://www.facebook.com/v25.0/dialog/oauth?client_id=test",
      ),
    );
    expect(await screen.findByText("Instagram @etchnshine connected; messaging disabled"))
      .toBeInTheDocument();
    expect(screen.queryByLabelText("Temporary Meta authorization address"))
      .not.toBeInTheDocument();
    delete window.__TAURI_INTERNALS__;
  });

  it("uploads a Shopify listing CSV into the local catalogue", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Catalogue/ }));
    await user.click(screen.getByRole("tab", { name: "Import catalogue" }));
    const file = new File(
      ["Handle,Title\npersonalised-topper,Personalised Topper"],
      "products_export.csv",
      { type: "text/csv" },
    );
    const fileInput = screen.getByLabelText("Shopify product export");
    await user.upload(fileInput, file);
    const importButton = screen.getByRole("button", { name: "Import locally" });
    expect(importButton).toBeEnabled();
    const importForm = importButton.closest("form");
    if (!importForm) throw new Error("Shopify import form is missing.");
    fireEvent.submit(importForm);
    await waitFor(() =>
      expect(api.importShopifyCsv).toHaveBeenCalledWith(
        "products_export.csv",
        expect.stringContaining("personalised-topper"),
      ),
    );
    expect(await screen.findByText("Shopify CSV processed")).toBeInTheDocument();
  });

  it("paginates the catalogue and resets pagination when filtering", async () => {
    const user = userEvent.setup();
    const catalogue = Array.from({ length: 13 }, (_, index) => ({
      ...product,
      id: `catalogue-product-${index + 1}`,
      shopify_handle: `catalogue-product-${index + 1}`,
      name: `Catalogue Product ${String(index + 1).padStart(2, "0")}`,
    }));
    vi.mocked(api.products).mockResolvedValue(catalogue);

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Catalogue/ }));

    const pagination = await screen.findByRole("navigation", { name: "products pagination" });
    expect(within(pagination).getByText("Showing 1–8 of 13 products")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Catalogue Product 01" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Catalogue Product 13" })).not.toBeInTheDocument();

    await user.click(within(pagination).getByRole("button", { name: "Next products page" }));
    expect(await screen.findByRole("heading", { name: "Catalogue Product 13" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Catalogue Product 01" })).not.toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "Search catalogue" }), "Product 01");
    expect(await screen.findByRole("heading", { name: "Catalogue Product 01" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "products pagination" })).not.toBeInTheDocument();
  });

  it("moves between pages in the pipeline lead selector", async () => {
    const user = userEvent.setup();
    const pipelineLeads = Array.from({ length: 15 }, (_, index) => ({
      ...lead,
      id: `pipeline-lead-${index + 1}`,
      business_name: `Pipeline Lead ${String(index + 1).padStart(2, "0")}`,
    }));
    vi.mocked(api.leads).mockResolvedValue(pipelineLeads);

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));

    const pagination = await screen.findByRole("navigation", { name: "pipeline leads pagination" });
    expect(within(pagination).getByText("Showing 1–8 of 15 pipeline leads")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pipeline Lead 01/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pipeline Lead 15/ })).not.toBeInTheDocument();

    await user.click(within(pagination).getByRole("button", { name: "Next pipeline leads page" }));
    expect(await screen.findByRole("button", { name: /Pipeline Lead 15/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pipeline Lead 01/ })).not.toBeInTheDocument();
  });

  it("recalculates a deterministic score from the pipeline", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));
    await user.click(screen.getByRole("tab", { name: "Score & products" }));
    expect(screen.getByText("72/100")).toBeInTheDocument();
    expect(screen.getByText("Business relevance")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate score" }));
    await waitFor(() => expect(api.calculateScore).toHaveBeenCalledWith(lead.id, campaign.id));
  });

  it("records a weekly shortlist approval without sending outreach", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Weekly shortlist/ }));
    expect(screen.getByRole("heading", { name: /Luton Bakery Partnerships/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(api.shortlistAction).toHaveBeenCalledWith(
        shortlist.id,
        shortlist.items[0]?.id,
        "approved",
        undefined,
      ),
    );
  });

  it("adds, edits and deletes a message template", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Templates/ }));
    expect(screen.getByRole("heading", { name: "Follow-up" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Add template" }));
    await user.type(screen.getByRole("textbox", { name: "Topic" }), "Introduction");
    await user.type(
      screen.getByRole("textbox", { name: /Subject/ }),
      "Hello from Etch N Shine",
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Body" }), {
      target: { value: "Hi {{business_name}}, introducing ourselves." },
    });
    await user.click(screen.getByRole("button", { name: "Add template" }));
    await waitFor(() =>
      expect(api.createTemplate).toHaveBeenCalledWith({
        topic: "Introduction",
        subject: "Hello from Etch N Shine",
        body: "Hi {{business_name}}, introducing ourselves.",
        product_family_ids: [],
      }),
    );

    await user.click(screen.getByText("Edit template"));
    const bodyField = screen.getByRole("textbox", { name: "Body" });
    await user.clear(bodyField);
    await user.type(bodyField, "Updated body text.");
    await user.click(screen.getByRole("button", { name: "Save template" }));
    await waitFor(() =>
      expect(api.updateTemplate).toHaveBeenCalledWith(
        template.id,
        expect.objectContaining({ body: "Updated body text." }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(api.deleteTemplate).toHaveBeenCalledWith(template.id));
  });

  it("sends a WhatsApp, email and Instagram message from a lead's Contact tab", async () => {
    const user = userEvent.setup();
    vi.mocked(openUrl).mockResolvedValue(undefined);
    window.__TAURI_INTERNALS__ = {};
    vi.mocked(api.leads).mockResolvedValue([
      {
        ...lead,
        phone_number: "+44 7438 186906",
        public_email: "hello@example.test",
        social_identities: [
          {
            id: "identity-1",
            platform: "instagram",
            profile_url: "https://www.instagram.com/examplecakes",
            normalized_handle: "examplecakes",
            source_url: null,
            classification: "user_observed",
            collected_at: "2026-07-18T10:00:00Z",
          },
        ],
      },
    ]);

    try {
      render(<App />);
      await screen.findByText("API connected");
      await user.click(screen.getByRole("link", { name: /Pipeline/ }));
      await user.click(screen.getByRole("tab", { name: "Contact" }));
      await user.selectOptions(screen.getByRole("combobox", { name: "Template" }), template.id);

      expect(
        screen.getByText("Hi Example Celebration Cakes, checking in about your order."),
      ).toBeInTheDocument();

      const expectedBody = "Hi Example Celebration Cakes, checking in about your order.";

      await user.click(screen.getByRole("button", { name: "WhatsApp" }));
      await waitFor(() =>
        expect(openUrl).toHaveBeenLastCalledWith(
          expect.stringContaining("https://wa.me/447438186906?text="),
        ),
      );
      await waitFor(() =>
        expect(api.addCommunication).toHaveBeenLastCalledWith(lead.id, {
          channel: "whatsapp",
          content: expectedBody,
          sent_status: "recorded",
        }),
      );

      await user.click(screen.getByRole("button", { name: "Email" }));
      await waitFor(() =>
        expect(openUrl).toHaveBeenLastCalledWith(
          expect.stringContaining("mailto:hello@example.test?subject="),
        ),
      );
      await waitFor(() =>
        expect(api.addCommunication).toHaveBeenLastCalledWith(lead.id, {
          channel: "email",
          content: expectedBody,
          subject: "Following up, Example Celebration Cakes",
          sent_status: "recorded",
        }),
      );

      await user.click(screen.getByRole("button", { name: "Instagram" }));
      await waitFor(() =>
        expect(openUrl).toHaveBeenLastCalledWith("https://ig.me/m/examplecakes"),
      );
      await waitFor(() =>
        expect(api.addCommunication).toHaveBeenLastCalledWith(lead.id, {
          channel: "instagram",
          content: expectedBody,
          sent_status: "recorded",
        }),
      );
    } finally {
      delete window.__TAURI_INTERNALS__;
    }
  });

  it("fills {{products}} with every product from a template's assigned product families", async () => {
    const user = userEvent.setup();
    const familyTemplate = {
      ...template,
      id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      topic: "Introductory offer",
      body: "Hi {{business_name}}, take a look:\n{{products}}",
      product_family_ids: [productFamily.id],
    };
    vi.mocked(api.templates).mockResolvedValue([template, familyTemplate]);

    render(<App />);
    await screen.findByText("API connected");
    await user.click(screen.getByRole("link", { name: /Pipeline/ }));
    await user.click(screen.getByRole("tab", { name: "Contact" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Template" }),
      familyTemplate.id,
    );

    const previewBody = screen.getByText(/take a look/);
    expect(previewBody.textContent).toBe(
      `Hi Example Celebration Cakes, take a look:\n${product.name} — ${product.pricing_guidance}`,
    );
  });
});
