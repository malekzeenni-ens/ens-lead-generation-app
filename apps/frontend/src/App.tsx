import {
  AlertTriangle,
  Database,
  FileText,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  Megaphone,
  PackageSearch,
  RefreshCw,
  Settings,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useEffect, useRef, useState } from "react";

import brandMarkUrl from "../../desktop/brand-logo.png";
import {
  ApiError,
  api,
  type CampaignRunProvider,
  type CampaignInput,
  type CampaignUpdate,
  type LeadInput,
  type LeadUpdate,
  type ProductFamilyInput,
  type ProductFamilyUpdate,
  type ProductInput,
  type ProductUpdate,
  type SocialCandidateInput,
  type TemplateInput,
  type TemplateUpdate,
} from "./api";
import { CatalogueWorkspace } from "./components/CatalogueWorkspace";
import { CampaignWorkspace } from "./components/CampaignWorkspace";
import { ConnectionBadge, type HealthState, NavigationItem } from "./components/DesignSystem";
import { DashboardWorkspace } from "./components/DashboardWorkspace";
import { LeadWorkspace } from "./components/LeadWorkspace";
import { PipelineWorkspace } from "./components/PipelineWorkspace";
import { SettingsWorkspace } from "./components/SettingsWorkspace";
import { ShortlistWorkspace } from "./components/ShortlistWorkspace";
import { TemplatesWorkspace } from "./components/TemplatesWorkspace";
import { BAKERY_SEGMENT, type WorkspaceSection } from "./domain";
import { WorkspaceActionsContext, type WorkspaceActions } from "./WorkspaceActionsContext";
import type {
  AutomationCapabilities,
  BackupResult,
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
  ScoringWeights,
  ShopifyImportResult,
  Shortlist,
  Template,
  VerificationResult,
  WorkspaceSettings,
} from "./types";

async function openExternalUrl(url: string): Promise<void> {
  if (window.__TAURI_INTERNALS__) {
    await openUrl(url);
    return;
  }
  const browser = window.open(url, "_blank", "noopener,noreferrer");
  if (!browser) throw new Error("The browser blocked the external window.");
}

const SECTION_LABELS: Record<WorkspaceSection, string> = {
  overview: "Overview",
  campaigns: "Campaigns",
  leads: "All leads",
  catalogue: "Catalogue",
  templates: "Templates",
  shortlist: "Weekly shortlist",
  pipeline: "Pipeline",
  settings: "Settings",
};

const NOTIFICATION_MIN_MS = 5_000;
const NOTIFICATION_MAX_MS = 12_000;
const NOTIFICATION_MS_PER_CHARACTER = 60;

/** Longer toasts (e.g. errors with field-level detail) stay up longer, up to a cap. */
function notificationDurationMs(message: string): number {
  return Math.min(
    NOTIFICATION_MAX_MS,
    Math.max(NOTIFICATION_MIN_MS, message.length * NOTIFICATION_MS_PER_CHARACTER),
  );
}

/**
 * The single resources a mutation should re-fetch afterward, instead of the
 * full 13-endpoint `refresh()`. Keeps a quick note-add from re-fetching the
 * whole catalogue; the full refresh still runs on mount, manual Refresh, and
 * campaign-run/Meta-auth completion, which resync anything left out here.
 */
type RefreshDomain =
  | "campaigns"
  | "leads"
  | "products"
  | "scoringProfile"
  | "scores"
  | "shortlists"
  | "campaignRuns"
  | "capabilities"
  | "metaConnection"
  | "settings"
  | "diagnostics"
  | "summary"
  | "templates"
  | "productFamilies";

function validationDetails(error: ApiError): string[] {
  const errors = error.details.details.errors;
  if (!Array.isArray(errors)) return [];
  return errors
    .map((entry) => {
      if (typeof entry !== "object" || entry === null) return null;
      const record = entry as Record<string, unknown>;
      const message = typeof record.message === "string" ? record.message : null;
      if (!message) return null;
      const location = Array.isArray(record.location)
        ? record.location.filter((segment) => segment !== "body").join(".")
        : "";
      return location ? `${location}: ${message}` : message;
    })
    .filter((entry): entry is string => entry !== null);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const base = `${error.message} Reference: ${error.details.correlation_id}`;
    const details = validationDetails(error);
    return details.length > 0 ? `${base} — ${details.join("; ")}` : base;
  }
  if (error instanceof Error) return error.message;
  if (typeof error === "string" && error.trim()) return error;
  // Some native/plugin rejections (e.g. Tauri's opener plugin) reject with a
  // plain object rather than a real Error; surface its message if it has one
  // instead of a dead-end generic string.
  if (typeof error === "object" && error !== null && "message" in error) {
    const { message } = error;
    if (typeof message === "string" && message.trim()) return message;
  }
  return "An unexpected error occurred.";
}

export default function App() {
  const workspaceContentRef = useRef<HTMLElement>(null);
  const [health, setHealth] = useState<HealthState>("checking");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignRuns, setCampaignRuns] = useState<CampaignRun[]>([]);
  const [automationCapabilities, setAutomationCapabilities] =
    useState<AutomationCapabilities | null>(null);
  const [metaConnection, setMetaConnection] = useState<MetaConnection | null>(null);
  const [metaAuthorizationUrl, setMetaAuthorizationUrl] = useState<string | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [scores, setScores] = useState<ScoreRun[]>([]);
  const [shortlists, setShortlists] = useState<Shortlist[]>([]);
  const [scoringProfile, setScoringProfile] = useState<ScoringProfile | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [productFamilies, setProductFamilies] = useState<ProductFamily[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>("overview");
  const [campaignLandingTask, setCampaignLandingTask] = useState<"campaigns" | "create">(
    "campaigns",
  );
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [leadsLandingFilter, setLeadsLandingFilter] = useState<"" | "review">("");

  async function refresh(showLoading = false): Promise<void> {
    if (showLoading) setLoading(true);
    try {
      const [
        healthResult,
        campaignResult,
        leadResult,
        summaryResult,
        settingsResult,
        diagnosticsResult,
        productResult,
        scoreResult,
        shortlistResult,
        profileResult,
        campaignRunResult,
        capabilityResult,
        metaConnectionResult,
        templateResult,
        productFamilyResult,
      ] =
        await Promise.all([
          api.health(),
          api.campaigns(),
          api.leads(),
          api.summary(),
          api.settings(),
          api.diagnostics(),
          api.products(),
          api.latestScores(),
          api.shortlists(),
          api.scoringProfile(BAKERY_SEGMENT),
          api.campaignRuns(),
          api.automationCapabilities(),
          api.metaConnection(),
          api.templates(),
          api.productFamilies(),
        ]);
      setHealth(healthResult.status === "ok" ? "connected" : "unavailable");
      setCampaigns(campaignResult);
      setLeads(leadResult);
      setSummary(summaryResult);
      setSettings(settingsResult);
      setDiagnostics(diagnosticsResult);
      setProducts(productResult);
      setScores(scoreResult);
      setShortlists(shortlistResult);
      setScoringProfile(profileResult);
      setCampaignRuns(campaignRunResult);
      setAutomationCapabilities(capabilityResult);
      setMetaConnection(metaConnectionResult);
      setTemplates(templateResult);
      setProductFamilies(productFamilyResult);
      setSelectedLeadId((current) =>
        current && leadResult.some((lead) => lead.id === current) ? current : (leadResult[0]?.id ?? null),
      );
      setError(null);
    } catch (caught) {
      setHealth("unavailable");
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  const domainRefreshers: Record<RefreshDomain, () => Promise<void>> = {
    campaigns: async () => setCampaigns(await api.campaigns()),
    leads: async () => {
      const result = await api.leads();
      setLeads(result);
      setSelectedLeadId((current) =>
        current && result.some((lead) => lead.id === current) ? current : (result[0]?.id ?? null),
      );
    },
    products: async () => setProducts(await api.products()),
    scoringProfile: async () => setScoringProfile(await api.scoringProfile(BAKERY_SEGMENT)),
    scores: async () => setScores(await api.latestScores()),
    shortlists: async () => setShortlists(await api.shortlists()),
    campaignRuns: async () => setCampaignRuns(await api.campaignRuns()),
    capabilities: async () => setAutomationCapabilities(await api.automationCapabilities()),
    metaConnection: async () => setMetaConnection(await api.metaConnection()),
    settings: async () => setSettings(await api.settings()),
    diagnostics: async () => setDiagnostics(await api.diagnostics()),
    summary: async () => setSummary(await api.summary()),
    templates: async () => setTemplates(await api.templates()),
    productFamilies: async () => setProductFamilies(await api.productFamilies()),
  };

  async function refreshDomains(domains: RefreshDomain[]): Promise<void> {
    await Promise.all(domains.map((domain) => domainRefreshers[domain]()));
  }

  useEffect(() => {
    void refresh(true);
  }, []);

  useEffect(() => {
    if (!success) return;
    const timer = window.setTimeout(() => setSuccess(null), notificationDurationMs(success));
    return () => window.clearTimeout(timer);
  }, [success]);

  useEffect(() => {
    if (!error) return;
    const timer = window.setTimeout(() => setError(null), notificationDurationMs(error));
    return () => window.clearTimeout(timer);
  }, [error]);

  useEffect(() => {
    const workspace = workspaceContentRef.current;
    if (workspace) {
      workspace.scrollTop = 0;
      workspace.focus({ preventScroll: true });
    }
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [activeSection]);

  const activeCampaignRuns = campaignRuns.filter((run) =>
    ["queued", "running"].includes(run.status),
  );
  const hasActiveCampaignRun = activeCampaignRuns.length > 0;

  useEffect(() => {
    if (!hasActiveCampaignRun) return;
    const timer = window.setInterval(() => {
      void api
        .campaignRuns()
        .then((currentRuns) => {
          setCampaignRuns(currentRuns);
          if (!currentRuns.some((run) => ["queued", "running"].includes(run.status))) {
            void refresh();
          }
        })
        .catch((caught: unknown) => setError(errorMessage(caught)));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [hasActiveCampaignRun]);

  useEffect(() => {
    if (metaConnection?.status !== "authorization_pending") return;
    const timer = window.setInterval(() => {
      void api
        .metaConnection()
        .then((current) => {
          setMetaConnection(current);
          if (current.status !== "authorization_pending") {
            setMetaAuthorizationUrl(null);
            void api
              .automationCapabilities()
              .then(setAutomationCapabilities)
              .catch((caught: unknown) => setError(errorMessage(caught)));
            void refresh();
          }
        })
        .catch((caught: unknown) => setError(errorMessage(caught)));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [metaConnection?.status]);

  useEffect(() => {
    const syncProviderConnections = (): void => {
      void Promise.all([api.metaConnection(), api.automationCapabilities()])
        .then(([connection, capabilities]) => {
          setMetaConnection(connection);
          setAutomationCapabilities(capabilities);
          if (connection.status !== "authorization_pending") setMetaAuthorizationUrl(null);
        })
        .catch((caught: unknown) => setError(errorMessage(caught)));
    };
    window.addEventListener("focus", syncProviderConnections);
    return () => window.removeEventListener("focus", syncProviderConnections);
  }, []);

  async function perform<T>(
    operation: () => Promise<T>,
    message: string,
    domains: RefreshDomain[],
  ): Promise<T | null> {
    setBusy(true);
    setSuccess(null);
    setError(null);
    try {
      const result = await operation();
      await refreshDomains(domains);
      setSuccess(message);
      return result;
    } catch (caught) {
      setError(errorMessage(caught));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function createCampaign(data: CampaignInput): Promise<boolean> {
    return (
      (await perform(
        () => api.createCampaign(data),
        "Campaign created and stored locally.",
        ["campaigns", "summary"],
      )) !== null
    );
  }

  async function updateCampaign(campaignId: string, data: CampaignUpdate): Promise<boolean> {
    return (
      (await perform(
        () => api.updateCampaign(campaignId, data),
        "Campaign changes saved with audit history.",
        ["campaigns", "summary"],
      )) !== null
    );
  }

  async function duplicateCampaign(campaignId: string, name: string): Promise<boolean> {
    return (
      (await perform(
        () => api.duplicateCampaign(campaignId, name),
        "Paused campaign copy created.",
        ["campaigns", "summary"],
      )) !== null
    );
  }

  async function runCampaign(
    campaignId: string,
    provider: CampaignRunProvider,
  ): Promise<boolean> {
    const providerLabel =
      provider === "google_places"
        ? "Google Places"
        : provider === "instagram"
          ? "Instagram profile refresh"
          : "Scoring";
    return (
      (await perform(
        () => api.startCampaignRun(campaignId, provider),
        `${providerLabel} run started. Only the selected discovery source will run before scoring and shortlist preparation.`,
        ["campaignRuns"],
      )) !== null
    );
  }

  async function runAllCampaigns(provider: CampaignRunProvider): Promise<boolean> {
    const providerLabel =
      provider === "google_places"
        ? "Google Places"
        : provider === "instagram"
          ? "Instagram profile refresh"
          : "Scoring";
    return (
      (await perform(
        () => api.startAllCampaignRuns(provider),
        `${providerLabel} queued for eligible active campaigns. Other discovery providers will not run.`,
        ["campaignRuns"],
      )) !== null
    );
  }

  async function captureSocialCandidate(data: SocialCandidateInput): Promise<boolean> {
    return (
      (await perform(
        () => api.captureSocialCandidate(data),
        "Social lead captured, deduplicated, scored and checked for the weekly shortlist.",
        ["campaignRuns"],
      )) !== null
    );
  }

  async function previewInstagramProfile(
    profileUrl: string,
  ): Promise<InstagramProfilePreview | null> {
    setBusy(true);
    setSuccess(null);
    setError(null);
    try {
      const profile = await api.previewInstagramProfile(profileUrl);
      setSuccess(`Meta found the professional profile @${profile.username}. Review it below.`);
      return profile;
    } catch (caught) {
      setError(errorMessage(caught));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function importInstagramProfile(
    campaignId: string,
    profileUrl: string,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.importInstagramProfile(campaignId, profileUrl),
        "Instagram profile imported, deduplicated, scored and checked for the shortlist.",
        ["campaignRuns"],
      )) !== null
    );
  }

  async function enrichKnownInstagramProfiles(campaignId: string): Promise<boolean> {
    return (
      (await perform(
        () => api.enrichKnownInstagramProfiles(campaignId),
        "Saved Instagram profiles were rechecked through Meta, deduplicated and rescored.",
        ["campaignRuns"],
      )) !== null
    );
  }

  async function openSocialSearch(url: string): Promise<boolean> {
    setSuccess(null);
    setError(null);
    try {
      await openExternalUrl(url);
      setSuccess(
        "Public social search opened in your browser. Review a profile, then capture its details here.",
      );
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    }
  }

  async function sendContactMessage(
    leadId: string,
    channel: "whatsapp" | "email" | "instagram",
    url: string,
    channelLabel: string,
    content: string,
    subject?: string,
  ): Promise<boolean> {
    setSuccess(null);
    setError(null);
    try {
      await openExternalUrl(url);
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    }
    return (
      (await perform(
        () =>
          api.addCommunication(leadId, {
            channel,
            content,
            ...(subject ? { subject } : {}),
            sent_status: "recorded",
          }),
        `${channelLabel} opened with the selected template and logged to the lead's activity history.`,
        ["leads"],
      )) !== null
    );
  }

  async function cancelCampaignRun(runId: string): Promise<boolean> {
    return (
      (await perform(
        () => api.cancelCampaignRun(runId),
        "Campaign run cancellation requested.",
        ["campaignRuns"],
      )) !== null
    );
  }

  async function decideDiscoveryCandidate(
    candidateId: string,
    action: "promote" | "link" | "reject",
    leadId?: string,
  ): Promise<boolean> {
    const reason = action === "reject" ? "Rejected during operator duplicate review." : undefined;
    return (
      (await perform(
        () => api.decideDiscoveryCandidate(candidateId, action, leadId, reason),
        "Discovery candidate decision saved with audit history.",
        ["campaignRuns", "leads", "summary"],
      )) !== null
    );
  }

  async function createLead(data: LeadInput): Promise<boolean> {
    const result = await perform(
      () => api.createLead(data),
      "Lead added with source evidence and audit history.",
      ["leads", "summary"],
    );
    if (result) setSelectedLeadId(result.id);
    return result !== null;
  }

  async function updateLead(leadId: string, data: LeadUpdate): Promise<boolean> {
    return (
      (await perform(() => api.updateLead(leadId, data), "Lead details saved.", [
        "leads",
        "summary",
      ])) !== null
    );
  }

  async function changeLeadStage(
    leadId: string,
    stage: string,
    reason?: string,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.changeLeadStage(leadId, stage, reason),
        "Pipeline stage changed and recorded.",
        ["leads", "summary"],
      )) !== null
    );
  }

  async function addNote(leadId: string, content: string): Promise<boolean> {
    return (
      (await perform(
        () => api.addLeadNote(leadId, content),
        "Note added to the activity timeline.",
        ["leads"],
      )) !== null
    );
  }

  async function addFollowUp(leadId: string, data: Record<string, unknown>): Promise<boolean> {
    return (
      (await perform(
        () => api.addFollowUp(leadId, data),
        "Follow-up added to the operating queue.",
        ["leads", "summary"],
      )) !== null
    );
  }

  async function completeFollowUp(leadId: string, followUpId: string): Promise<boolean> {
    return (
      (await perform(
        () => api.completeFollowUp(leadId, followUpId),
        "Follow-up completed.",
        ["leads", "summary"],
      )) !== null
    );
  }

  async function addCommunication(
    leadId: string,
    data: Record<string, unknown>,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.addCommunication(leadId, data),
        "Manual communication added to the timeline.",
        ["leads"],
      )) !== null
    );
  }

  async function suppressLead(leadId: string, data: Record<string, unknown>): Promise<boolean> {
    return (
      (await perform(
        () => api.suppressLead(leadId, data),
        "Suppression applied; outreach actions are blocked.",
        ["leads", "summary"],
      )) !== null
    );
  }

  async function liftSuppression(leadId: string): Promise<boolean> {
    return (
      (await perform(
        () => api.liftSuppression(leadId),
        "Suppression lifted; review the pipeline stage before contact.",
        ["leads", "summary"],
      )) !== null
    );
  }

  async function deleteLead(leadId: string): Promise<boolean> {
    const result = await perform(
      () => api.deleteLead(leadId),
      "Lead data deleted; active suppression evidence was retained where required.",
      ["leads", "summary"],
    );
    if (result) setSelectedLeadId(null);
    return result !== null;
  }

  async function saveSettings(data: Partial<WorkspaceSettings>): Promise<boolean> {
    return (
      (await perform(() => api.updateSettings(data), "Workspace settings saved.", [
        "settings",
      ])) !== null
    );
  }

  async function configureMeta(appId: string, appSecret: string): Promise<boolean> {
    return (
      (await perform(
        () => api.configureMeta(appId, appSecret),
        "Meta application credentials were encrypted for this Windows user.",
        ["metaConnection", "capabilities"],
      )) !== null
    );
  }

  async function startMetaAuthorization(): Promise<boolean> {
    setBusy(true);
    setSuccess(null);
    setError(null);
    try {
      const result = await api.startMetaAuthorization();
      setMetaAuthorizationUrl(result.authorization_url);
      await openExternalUrl(result.authorization_url);
      const current = await api.metaConnection();
      setMetaConnection(current);
      if (current.status !== "authorization_pending") {
        setAutomationCapabilities(await api.automationCapabilities());
        setMetaAuthorizationUrl(null);
      }
      setSuccess("Meta authorization opened in your browser. Complete it there, then return here.");
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function selectMetaAccount(pageId: string): Promise<boolean> {
    return (
      (await perform(
        () => api.selectMetaAccount(pageId),
        "Instagram professional account selected for campaign discovery.",
        ["metaConnection", "capabilities"],
      )) !== null
    );
  }

  async function disconnectMeta(removeConfiguration = false): Promise<boolean> {
    return (
      (await perform(
        () => (removeConfiguration ? api.removeMetaConfiguration() : api.disconnectMeta()),
        removeConfiguration
          ? "Meta credentials and tokens were removed from the local encrypted vault."
          : "Meta access tokens were removed; the encrypted app credentials were retained.",
        ["metaConnection", "capabilities"],
      )) !== null
    );
  }

  async function exportLeads(format: "csv" | "json"): Promise<boolean> {
    setBusy(true);
    setSuccess(null);
    setError(null);
    try {
      const result = await api.exportLeads(format);
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSuccess(`${format.toUpperCase()} export prepared locally.`);
      return true;
    } catch (caught) {
      setError(errorMessage(caught));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function createBackup(targetDirectory: string): Promise<BackupResult | null> {
    return perform(
      () => api.createBackup(targetDirectory),
      "Verified backup and checksum manifest created.",
      ["diagnostics"],
    );
  }

  async function verifyBackup(backupPath: string): Promise<VerificationResult | null> {
    return perform(() => api.verifyBackup(backupPath), "Backup verification completed.", []);
  }

  async function importShopifyCsv(
    filename: string,
    content: string,
  ): Promise<ShopifyImportResult | null> {
    return perform(
      () => api.importShopifyCsv(filename, content),
      "Shopify catalogue CSV imported and matched by product handle.",
      ["products", "summary"],
    );
  }

  async function createProduct(data: ProductInput): Promise<boolean> {
    return (
      (await perform(() => api.createProduct(data), "Catalogue product added.", [
        "products",
        "summary",
      ])) !== null
    );
  }

  async function updateProduct(productId: string, data: ProductUpdate): Promise<boolean> {
    return (
      (await perform(
        () => api.updateProduct(productId, data),
        "Catalogue product changes saved.",
        ["products", "summary"],
      )) !== null
    );
  }

  async function updateScoringProfile(
    name: string,
    weights: ScoringWeights,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.updateScoringProfile(BAKERY_SEGMENT, name, weights),
        "A new immutable scoring profile version was created.",
        ["scoringProfile"],
      )) !== null
    );
  }

  async function createTemplate(data: TemplateInput): Promise<boolean> {
    return (
      (await perform(() => api.createTemplate(data), "Template added.", ["templates"])) !== null
    );
  }

  async function updateTemplate(templateId: string, data: TemplateUpdate): Promise<boolean> {
    return (
      (await perform(
        () => api.updateTemplate(templateId, data),
        "Template changes saved.",
        ["templates"],
      )) !== null
    );
  }

  async function deleteTemplate(templateId: string): Promise<boolean> {
    return (
      (await perform(() => api.deleteTemplate(templateId), "Template deleted.", [
        "templates",
      ])) !== null
    );
  }

  async function createProductFamily(data: ProductFamilyInput): Promise<boolean> {
    return (
      (await perform(
        () => api.createProductFamily(data),
        "Product family created.",
        ["productFamilies"],
      )) !== null
    );
  }

  async function updateProductFamily(
    familyId: string,
    data: ProductFamilyUpdate,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.updateProductFamily(familyId, data),
        "Product family changes saved.",
        ["productFamilies"],
      )) !== null
    );
  }

  async function deleteProductFamily(familyId: string): Promise<boolean> {
    return (
      (await perform(() => api.deleteProductFamily(familyId), "Product family deleted.", [
        "productFamilies",
        "campaigns",
      ])) !== null
    );
  }

  async function calculateScore(leadId: string, campaignId: string): Promise<boolean> {
    return (
      (await perform(
        () => api.calculateScore(leadId, campaignId),
        "Deterministic score and product matches calculated.",
        ["scores", "leads", "summary"],
      )) !== null
    );
  }

  async function overrideScore(
    leadId: string,
    finalScore: number,
    reason: string,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.overrideScore(leadId, finalScore, reason),
        "Manual score override recorded without changing the calculated score.",
        ["scores", "leads", "summary"],
      )) !== null
    );
  }

  async function generateShortlist(
    campaignId: string,
    weekStart: string,
    size: number,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.generateShortlist(campaignId, weekStart, size),
        "Weekly shortlist generated with score and suppression controls.",
        ["shortlists", "leads", "summary"],
      )) !== null
    );
  }

  async function shortlistAction(
    shortlistId: string,
    itemId: string,
    action: string,
    reason?: string,
  ): Promise<boolean> {
    return (
      (await perform(
        () => api.shortlistAction(shortlistId, itemId, action, reason),
        `Shortlist item ${action} decision recorded.`,
        ["shortlists", "leads", "summary"],
      )) !== null
    );
  }

  function manageLead(leadId: string): void {
    setSelectedLeadId(leadId);
    setActiveSection("pipeline");
  }

  const actions: WorkspaceActions = {
    busy,
    loading,
    manageLead,
    goToCreateCampaign: () => {
      setCampaignLandingTask("create");
      setActiveSection("campaigns");
    },
    goToShortlist: () => setActiveSection("shortlist"),
    goToCampaigns: () => {
      setCampaignLandingTask("campaigns");
      setActiveSection("campaigns");
    },
    goToLeads: () => {
      setLeadsLandingFilter("");
      setActiveSection("leads");
    },
    goToLeadsNeedingReview: () => {
      setLeadsLandingFilter("review");
      setActiveSection("leads");
    },
    goToCatalogue: () => setActiveSection("catalogue"),
    createCampaign,
    updateCampaign,
    duplicateCampaign,
    runCampaign,
    runAllCampaigns,
    openSocialSearch,
    captureSocialCandidate,
    previewInstagramProfile,
    importInstagramProfile,
    enrichKnownInstagramProfiles,
    cancelCampaignRun,
    decideDiscoveryCandidate,
    createLead,
    updateLead,
    changeLeadStage,
    addNote,
    addFollowUp,
    completeFollowUp,
    addCommunication,
    suppressLead,
    liftSuppression,
    deleteLead,
    calculateScore,
    overrideScore,
    createProduct,
    updateProduct,
    importShopifyCsv,
    updateScoringProfile,
    generateShortlist,
    shortlistAction,
    saveSettings,
    exportLeads,
    createBackup,
    verifyBackup,
    configureMeta,
    startMetaAuthorization,
    selectMetaAccount,
    disconnectMeta,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    createProductFamily,
    updateProductFamily,
    deleteProductFamily,
    sendContactMessage,
  };

  const page = {
    overview: (
      <DashboardWorkspace
        campaigns={campaigns}
        leads={leads}
        summary={summary}
        shortlists={shortlists}
      />
    ),
    campaigns: (
      <CampaignWorkspace
        initialTask={campaignLandingTask}
        campaigns={campaigns}
        campaignRuns={campaignRuns}
        capabilities={automationCapabilities}
        settings={settings}
        productFamilies={productFamilies}
      />
    ),
    leads: (
      <LeadWorkspace
        campaigns={campaigns}
        leads={leads}
        initialClassificationFilter={leadsLandingFilter}
      />
    ),
    catalogue: (
      <CatalogueWorkspace
        products={products}
        scoringProfile={scoringProfile}
        productFamilies={productFamilies}
      />
    ),
    templates: (
      <TemplatesWorkspace templates={templates} productFamilies={productFamilies} />
    ),
    shortlist: <ShortlistWorkspace campaigns={campaigns} shortlists={shortlists} />,
    pipeline: (
      <PipelineWorkspace
        leads={leads}
        campaigns={campaigns}
        scores={scores}
        templates={templates}
        productFamilies={productFamilies}
        selectedLeadId={selectedLeadId}
        onSelectLead={setSelectedLeadId}
      />
    ),
    settings: (
      <SettingsWorkspace
        settings={settings}
        diagnostics={diagnostics}
        metaConnection={metaConnection}
        metaAuthorizationUrl={metaAuthorizationUrl}
      />
    ),
  } satisfies Record<WorkspaceSection, React.ReactNode>;

  return (
    <div className="application-frame">
      <a className="skip-link" href="#main-content">Skip to main content</a>

      <header className="application-header">
        <div className="brand-lockup">
          <img src={brandMarkUrl} alt="" width="40" height="40" />
          <div><span>Etch ’N’ Shine</span><strong>Lead generation</strong></div>
        </div>
        <div className="header-context" aria-label="Current workspace">
          <span>Workspace</span><strong>{SECTION_LABELS[activeSection]}</strong>
        </div>
        <div className="header-actions">
          <button
            className="secondary-action"
            type="button"
            title="Refresh workspace"
            onClick={() => void refresh(true)}
            disabled={busy || loading}
          >
            <RefreshCw className={loading ? "spin" : undefined} size={17} aria-hidden="true" />
            Refresh
          </button>
          {activeCampaignRuns.length > 0 ? (
            <div className="run-indicator" role="status" aria-live="polite">
              <RefreshCw className="spin" size={14} aria-hidden="true" />
              <span>
                {activeCampaignRuns.length === 1
                  ? `Running: ${activeCampaignRuns[0]?.campaign_name}`
                  : `${activeCampaignRuns.length} campaign runs in progress`}
              </span>
            </div>
          ) : null}
          <ConnectionBadge state={health} />
        </div>
      </header>

      <div className="workspace-shell">
        <aside className="sidebar">
          <nav aria-label="Workspace navigation">
            <p className="navigation-label">Lead acquisition</p>
            <NavigationItem href="#overview" icon={LayoutDashboard} label="Overview" active={activeSection === "overview"} onSelect={() => setActiveSection("overview")} />
            <NavigationItem href="#campaigns" icon={Megaphone} label="Campaigns" count={campaigns.length} active={activeSection === "campaigns"} onSelect={() => {
              setCampaignLandingTask("campaigns");
              setActiveSection("campaigns");
            }} />
            <NavigationItem href="#leads" icon={Users} label="All leads" count={leads.length} active={activeSection === "leads"} onSelect={() => setActiveSection("leads")} />

            <p className="navigation-label">Lead operations</p>
            <NavigationItem href="#shortlist" icon={ListChecks} label="Weekly shortlist" count={summary?.shortlisted_this_week} active={activeSection === "shortlist"} onSelect={() => setActiveSection("shortlist")} />
            <NavigationItem href="#pipeline" icon={GitBranch} label="Pipeline" count={summary?.open_follow_ups} active={activeSection === "pipeline"} onSelect={() => setActiveSection("pipeline")} />

            <p className="navigation-label">Configuration</p>
            <NavigationItem href="#catalogue" icon={PackageSearch} label="Catalogue" count={products.length} active={activeSection === "catalogue"} onSelect={() => setActiveSection("catalogue")} />
            <NavigationItem href="#templates" icon={FileText} label="Templates" count={templates.length} active={activeSection === "templates"} onSelect={() => setActiveSection("templates")} />
            <NavigationItem href="#settings" icon={Settings} label="Settings" active={activeSection === "settings"} onSelect={() => setActiveSection("settings")} />
          </nav>
          <div className="sidebar-control">
            <ShieldCheck size={20} aria-hidden="true" />
            <div>
              <strong>Controlled mode</strong>
              <p>
                {automationCapabilities?.google_places_configured ||
                automationCapabilities?.instagram_connected
                  ? "Connected discovery providers are available; AI and outbound messaging are off."
                  : "External providers, AI and outbound messaging are off."}
              </p>
            </div>
          </div>
          <div className="sidebar-footer">
            <Database size={16} aria-hidden="true" /><span>Local database</span><small>v0.1.0</small>
          </div>
        </aside>

        <main
          ref={workspaceContentRef}
          id="main-content"
          className="workspace-content"
          aria-busy={busy || loading}
          tabIndex={-1}
        >
          <p className="visually-hidden" role="status" aria-live="polite">
            {busy ? "Saving changes" : loading ? "Loading workspace" : "Workspace ready"}
          </p>
          {success ? (
            <div className="toast" role="status">
              <ShieldCheck size={18} aria-hidden="true" /><span>{success}</span>
              <button type="button" className="icon-button" aria-label="Dismiss notification" title="Dismiss notification" onClick={() => setSuccess(null)}><X size={17} /></button>
            </div>
          ) : null}
          {error ? (
            <div className="alert" role="alert">
              <AlertTriangle size={20} aria-hidden="true" />
              <div><strong>Action could not be completed</strong><p>{error}</p></div>
              <button className="secondary-action" type="button" onClick={() => setError(null)}>Dismiss</button>
            </div>
          ) : null}
          <WorkspaceActionsContext.Provider value={actions}>
            <div id={activeSection}>{page[activeSection]}</div>
          </WorkspaceActionsContext.Provider>
        </main>
      </div>

      <footer className="status-bar">
        <span><ShieldCheck size={14} aria-hidden="true" /> Operator-controlled mode</span>
        <span>
          {automationCapabilities?.instagram_connected
            ? `Instagram @${automationCapabilities.instagram_account} connected; messaging disabled`
            : automationCapabilities?.google_places_configured
              ? "Google discovery available; AI and messaging disabled"
              : "External discovery, AI and messaging disabled"}
        </span>
        <span>Etch ’N’ Shine · v0.1.0</span>
      </footer>
    </div>
  );
}
