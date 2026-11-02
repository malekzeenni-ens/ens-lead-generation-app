import {
  ArchiveRestore,
  AtSign,
  Bot,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  HardDrive,
  Info,
  KeyRound,
  Palette,
  MailCheck,
  MapPin,
  PlugZap,
  Save,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Smartphone,
  type LucideIcon,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import type {
  AutomationCapabilities,
  BackupResult,
  Diagnostics,
  MetaConnection,
  VerificationResult,
  WorkspaceSettings,
  CloudPolishStatus,
} from "../types";
import { humanize } from "../domain";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { useRememberedState } from "../remembered";
import { type DensityChoice, type ThemeChoice, useAppearance } from "../appearance";
import {
  HelpTip,
  LoadingState,
  PageHeader,
  StatGrid,
  StatusPill,
  type StatusTone,
} from "./DesignSystem";
import { PhoneAccessPanel } from "./PhoneAccessPanel";

type SettingsSection = "general" | "outreach" | "ai" | "connections" | "phone" | "data" | "about";

const SECTIONS: { id: SettingsSection; label: string; icon: LucideIcon }[] = [
  { id: "general", label: "General", icon: SlidersHorizontal },
  { id: "outreach", label: "Outreach", icon: MailCheck },
  { id: "ai", label: "AI and models", icon: Bot },
  { id: "connections", label: "Connections", icon: PlugZap },
  { id: "phone", label: "Phone access", icon: Smartphone },
  { id: "data", label: "Data and privacy", icon: Database },
  { id: "about", label: "About", icon: Info },
];

interface ConnectionCard {
  name: string;
  icon: LucideIcon;
  tone: StatusTone;
  status: string;
  detail: string;
}

interface SettingsWorkspaceProps {
  settings: WorkspaceSettings | null;
  diagnostics: Diagnostics | null;
  metaConnection: MetaConnection | null;
  metaAuthorizationUrl: string | null;
  cloudPolishStatus: CloudPolishStatus | null;
  capabilities?: AutomationCapabilities | null;
}

function formValue(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} bytes`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

// Mirrors ALLOWED_OLLAMA_MODELS in apps/backend/app/core/config.py. The backend rejects
// anything else, so both lists have to change together.
const LOCAL_AI_MODELS = [
  { id: "llama3.2:3b", label: "llama3.2:3b - fastest, lightest" },
  { id: "llama3.1:8b", label: "llama3.1:8b - better writing" },
  { id: "qwen3:8b", label: "qwen3:8b - better instruction following" },
  { id: "gemma3:12b", label: "gemma3:12b - strongest, slowest" },
] as const;


export function SettingsWorkspace({
  settings,
  diagnostics,
  metaConnection,
  metaAuthorizationUrl,
  cloudPolishStatus,
  capabilities = null,
}: SettingsWorkspaceProps) {
  const {
    loading,
    busy,
    saveSettings: onSave,
    exportLeads: onExport,
    createBackup: onBackup,
    verifyBackup: onVerifyBackup,
    configureMeta: onConfigureMeta,
    startMetaAuthorization: onStartMetaAuthorization,
    selectMetaAccount: onSelectMetaAccount,
    disconnectMeta: onDisconnectMeta,
    configureCloudPolish: onConfigureCloudPolish,
    removeCloudPolish: onRemoveCloudPolish,
  } = useWorkspaceActions();
  const [rememberedSection, setActiveTask] = useRememberedState<string>("settings:section", "general");
  const activeTask: SettingsSection = SECTIONS.some((section) => section.id === rememberedSection)
    ? (rememberedSection as SettingsSection)
    : "general";

  const connectionCards: ConnectionCard[] = [
    {
      name: "Instagram via Meta",
      icon: AtSign,
      ...(metaConnection?.connected
        ? { tone: "success" as const, status: "Connected", detail: metaConnection.selected_account ? `@${metaConnection.selected_account.instagram_username}` : "Choose an account below" }
        : metaConnection?.error_message || metaConnection?.status === "authorization_pending"
          ? { tone: "warning" as const, status: "Needs attention", detail: metaConnection.error_message ?? "Waiting for you to finish in the browser" }
          : metaConnection?.configured
            ? { tone: "warning" as const, status: "Needs attention", detail: "Credentials saved; connect to finish" }
            : { tone: "neutral" as const, status: "Not set up", detail: "Find and refresh Instagram leads" }),
    },
    {
      name: "Google Places",
      icon: MapPin,
      ...(capabilities?.google_places_configured
        ? { tone: "success" as const, status: "Connected", detail: `Up to ${capabilities.maximum_results_per_campaign} results per run` }
        : { tone: "neutral" as const, status: "Not set up", detail: "Set ENS_GOOGLE_PLACES_API_KEY for the service" }),
    },
    {
      name: "Cloud draft polish",
      icon: KeyRound,
      ...(cloudPolishStatus?.configured && cloudPolishStatus.enabled
        ? { tone: "success" as const, status: "Connected", detail: "On · one draft at a time" }
        : cloudPolishStatus?.configured
          ? { tone: "neutral" as const, status: "Saved, off", detail: "Turn on under AI and models" }
          : { tone: "neutral" as const, status: "Not set up", detail: "Optional; set up under AI and models" }),
    },
  ];
  const { theme, setTheme, density, setDensity } = useAppearance();
  const [backup, setBackup] = useState<BackupResult | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);

  async function saveSettings(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await onSave({
      retention_review_days: Number(formValue(form, "retention-days")),
      follow_up_window_days: Number(formValue(form, "follow-up-window")),
      default_campaign_radius_miles: Number(formValue(form, "default-radius")),
      default_weekly_shortlist_size: Number(formValue(form, "default-shortlist")),
    });
  }

  async function saveOutreachSettings(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await onSave({ weekly_outreach_global_limit: Number(formValue(form, "weekly-outreach-limit")) });
  }

  async function saveAiSettings(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await onSave({
      local_campaign_assistant_enabled: form.has("local-campaign-assistant-enabled"),
      protect_design_software_resources: form.has("protect-design-software-resources"),
      local_ai_model: formValue(form, "local-ai-model"),
    });
  }

  async function createBackup(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const result = await onBackup(formValue(new FormData(event.currentTarget), "backup-directory"));
    setBackup(result);
    setVerification(null);
  }

  async function verifyBackup(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const result = await onVerifyBackup(formValue(new FormData(event.currentTarget), "backup-path"));
    setVerification(result);
  }

  async function configureMeta(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const saved = await onConfigureMeta(
      formValue(form, "meta-app-id"),
      formValue(form, "meta-app-secret"),
    );
    if (saved) formElement.reset();
  }

  async function configureCloudPolish(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    // React clears currentTarget once the handler yields, so hold the element across awaits.
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const key = formValue(form, "cloud-api-key");
    if (key && !(await onConfigureCloudPolish(key))) return;
    const saved = await onSave({
      cloud_polish_enabled: form.has("cloud-polish-enabled"),
      cloud_polish_model: formValue(form, "cloud-polish-model"),
    });
    const keyInput = formElement.elements.namedItem("cloud-api-key");
    if (keyInput instanceof HTMLInputElement) keyInput.value = "";
    if (saved) formElement.reset();
  }

  async function selectMetaAccount(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await onSelectMetaAccount(formValue(new FormData(event.currentTarget), "meta-page-id"));
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="Defaults, connections, exports and app health."
      />

      <div className="settings-layout">
      <nav className="settings-nav" aria-label="Settings sections">
        {SECTIONS.map((section) => {
          const Icon = section.icon;
          return (
            <button
              key={section.id}
              type="button"
              aria-current={activeTask === section.id ? "page" : undefined}
              onClick={() => setActiveTask(section.id)}
            >
              <Icon size={17} aria-hidden="true" /> {section.label}
            </button>
          );
        })}
      </nav>

      <section className="workspace-section settings-content" aria-label={SECTIONS.find((section) => section.id === activeTask)?.label ?? "Settings"}>

        {loading || !settings ? (
          <div className="records-panel"><LoadingState label="Loading settings" /></div>
        ) : (
          <div key={activeTask} className="page-enter">
          <div className={`settings-grid${activeTask === "data" ? "" : " settings-grid--single"}`}>
            {activeTask === "phone" ? <PhoneAccessPanel /> : null}

            {activeTask === "connections" ? (
            <>
            <ul className="connection-cards" aria-label="Connection status">
              {connectionCards.map((card) => {
                const Icon = card.icon;
                return (
                  <li key={card.name} className="connection-card">
                    <span className="connection-card__icon" aria-hidden="true"><Icon size={18} /></span>
                    <div>
                      <strong>{card.name}</strong>
                      <small>{card.detail}</small>
                    </div>
                    <StatusPill tone={card.tone}>{card.status}</StatusPill>
                  </li>
                );
              })}
            </ul>
            <section className="form-panel settings-grid__wide" aria-labelledby="meta-settings-heading">
              <div className="subsection-heading">
                <div>
                  <h3 id="meta-settings-heading">Instagram via Meta</h3>
                  <p>Professional-profile lookup and refresh through your Meta app.</p>
                </div>
                <AtSign size={20} aria-hidden="true" />
              </div>

              {!metaConnection ? (
                <LoadingState label="Loading Meta connection" />
              ) : (
                <div className="provider-connection">
                  <div className="provider-connection__status">
                    <div>
                      <span
                        className={`status-badge${
                          metaConnection.connected ? " status-badge--success" : ""
                        }`}
                      >
                        {metaConnection.status.replaceAll("_", " ")}
                      </span>
                      {metaConnection.selected_account ? (
                        <p>
                          Using <strong>@{metaConnection.selected_account.instagram_username}</strong>
                          {" "}through {metaConnection.selected_account.page_name}
                        </p>
                      ) : (
                        <p>No Instagram professional account is selected yet.</p>
                      )}
                    </div>
                    <small>Graph API {metaConnection.graph_version}</small>
                  </div>

                  {!metaConnection.connected ? (
                  <div className="provider-connection__setup">
                    <p className="navigation-label">Setup</p>
                    <div className="form-notice">
                      <KeyRound size={17} aria-hidden="true" />
                      <div>
                        <strong>Valid OAuth Redirect URI</strong>
                        <p>
                          Add this exact value in Meta → Facebook Login → Settings before connecting:
                        </p>
                        <code>{metaConnection.callback_url}</code>
                      </div>
                    </div>

                    <form className="form-grid" onSubmit={(event) => void configureMeta(event)}>
                      <div className="field-pair">
                        <label>
                          Meta App ID
                          <input
                            name="meta-app-id"
                            inputMode="numeric"
                            pattern="[0-9]+"
                            required
                            autoComplete="off"
                            placeholder="Your numeric App ID"
                          />
                        </label>
                        <label>
                          Meta App Secret
                          <input
                            name="meta-app-secret"
                            type="password"
                            required
                            minLength={16}
                            autoComplete="new-password"
                            placeholder="Stored with Windows DPAPI"
                          />
                        </label>
                      </div>
                      <div className="form-actions">
                        <p>The secret and access tokens never enter SQLite or browser storage.</p>
                        <button className="secondary-action" type="submit" disabled={busy}>
                          <Save size={17} aria-hidden="true" />
                          {metaConnection.configured ? "Replace encrypted credentials" : "Save encrypted credentials"}
                        </button>
                      </div>
                    </form>

                    {metaConnection.configured ? (
                      <div className="provider-connection__actions">
                        <button
                          className="primary-action"
                          type="button"
                          disabled={busy || metaConnection.status === "authorization_pending"}
                          onClick={() => void onStartMetaAuthorization()}
                        >
                          <ExternalLink size={17} aria-hidden="true" />
                          {metaConnection.status === "authorization_pending"
                            ? "Waiting for Meta authorization"
                            : "Connect Instagram with Meta"}
                        </button>
                        <p>Only app admins, developers and testers are needed while the Meta app is unpublished.</p>
                      </div>
                    ) : null}

                    {metaAuthorizationUrl ? (
                      <div className="form-notice">
                        <ExternalLink size={17} aria-hidden="true" />
                        <div>
                          <strong>Manual browser fallback</strong>
                          <p>
                            If the browser did not open, copy this temporary address into your
                            browser. It expires after ten minutes.
                          </p>
                          <input
                            aria-label="Temporary Meta authorization address"
                            readOnly
                            value={metaAuthorizationUrl}
                            onFocus={(event) => event.currentTarget.select()}
                          />
                        </div>
                      </div>
                    ) : null}

                    {metaConnection.accounts.length > 1 && !metaConnection.selected_account ? (
                      <form
                        className="form-grid form-grid--compact"
                        onSubmit={(event) => void selectMetaAccount(event)}
                      >
                        <label>
                          Instagram account
                          <select name="meta-page-id" required defaultValue="">
                            <option value="">Select the Page/account pair</option>
                            {metaConnection.accounts.map((account) => (
                              <option key={account.page_id} value={account.page_id}>
                                @{account.instagram_username} — {account.page_name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button className="primary-action" type="submit" disabled={busy}>
                          Use selected account
                        </button>
                      </form>
                    ) : null}

                    {metaConnection.error_message ? (
                      <p className="automation-message automation-message--warning">
                        {metaConnection.error_message}
                      </p>
                    ) : null}
                  </div>
                  ) : null}

                  {metaConnection.configured ? (
                    <div className="provider-connection__actions">
                      <p className="navigation-label">Connection</p>
                      {metaConnection.connected ? (
                        <button
                          className="tertiary-action"
                          type="button"
                          disabled={busy}
                          onClick={() => void onDisconnectMeta(false)}
                        >
                          Disconnect access token
                        </button>
                      ) : null}
                      <button
                        className="tertiary-action"
                        type="button"
                        disabled={busy}
                        onClick={() => void onDisconnectMeta(true)}
                      >
                        Remove Meta credentials
                      </button>
                    </div>
                  ) : null}
                </div>
              )}
            </section>
            </>
            ) : null}

            {activeTask === "general" ? (
            <section className="form-panel">
              <div className="subsection-heading">
                <div><h3>General</h3><p>Defaults for new campaigns, and how far ahead Today looks.</p></div>
                <Settings size={19} aria-hidden="true" />
              </div>
              <form className="form-grid" onSubmit={(event) => void saveSettings(event)}>
                <div className="field-pair">
                  <label>Retention review interval
                    <span className="input-with-suffix"><input name="retention-days" type="number" min="30" max="3650" defaultValue={settings.retention_review_days} required /><span>days</span></span>
                  </label>
                  <label>Follow-up dashboard window
                    <span className="input-with-suffix"><input name="follow-up-window" type="number" min="1" max="30" defaultValue={settings.follow_up_window_days} required /><span>days</span></span>
                  </label>
                </div>
                <div className="field-pair">
                  <label>Default campaign radius
                    <span className="input-with-suffix"><input name="default-radius" type="number" min="1" max="500" defaultValue={settings.default_campaign_radius_miles} required /><span>miles</span></span>
                  </label>
                  <label>Default weekly shortlist
                    <input name="default-shortlist" type="number" min="1" max="50" defaultValue={settings.default_weekly_shortlist_size} required />
                  </label>
                </div>
                <button className="primary-action" type="submit" disabled={busy}><Save size={17} /> Save settings</button>
              </form>
            </section>
            ) : null}

            {activeTask === "general" ? (
            <section className="form-panel">
              <div className="subsection-heading">
                <div><h3>Appearance</h3><p>Applies straight away, on this computer only.</p></div>
                <Palette size={19} aria-hidden="true" />
              </div>
              <div className="form-grid">
                <fieldset className="choice-group">
                  <legend>Theme</legend>
                  {(
                    [
                      ["system", "Match Windows"],
                      ["light", "Bright"],
                      ["dark", "Dark"],
                    ] as [ThemeChoice, string][]
                  ).map(([value, label]) => (
                    <label key={value}>
                      <input type="radio" name="appearance-theme" checked={theme === value} onChange={() => setTheme(value)} />
                      {label}
                    </label>
                  ))}
                </fieldset>
                <fieldset className="choice-group">
                  <legend>Density</legend>
                  {(
                    [
                      ["comfortable", "Comfortable"],
                      ["compact", "Compact: more rows on screen"],
                    ] as [DensityChoice, string][]
                  ).map(([value, label]) => (
                    <label key={value}>
                      <input type="radio" name="appearance-density" checked={density === value} onChange={() => setDensity(value)} />
                      {label}
                    </label>
                  ))}
                </fieldset>
              </div>
            </section>
            ) : null}

            {activeTask === "outreach" ? (
            <section className="form-panel">
              <div className="subsection-heading">
                <div><h3>Outreach</h3><p>How much weekly automation may prepare. Every email still waits for your approval and is sent by you from Zoho.</p></div>
                <MailCheck size={19} aria-hidden="true" />
              </div>
              <form className="form-grid" onSubmit={(event) => void saveOutreachSettings(event)}>
                <label>
                  <span className="field-label-with-help">
                    Maximum automatic drafts per week
                    <HelpTip label="About the automatic weekly draft limit">
                      This is one shared limit across all enabled campaigns. Duplicate leads are
                      removed before the limit is applied, and skipped leads remain available for
                      a later week.
                    </HelpTip>
                  </span>
                  <input name="weekly-outreach-limit" type="number" min="1" max="100" defaultValue={settings.weekly_outreach_global_limit} required />
                  <small className="field-hint">Start with 2–3 drafts while testing, then increase it when the review workload feels comfortable.</small>
                </label>
                <button className="primary-action" type="submit" disabled={busy}><Save size={17} /> Save outreach settings</button>
              </form>
            </section>
            ) : null}

            {activeTask === "ai" ? (
            <>
            <section className="form-panel">
              <div className="subsection-heading">
                <div><h3>Local AI</h3><p>The assistant runs on this computer through Ollama.</p></div>
                <Bot size={19} aria-hidden="true" />
              </div>
              <form className="form-grid" onSubmit={(event) => void saveAiSettings(event)}>
                <label className="choice-row">
                  <input
                    name="local-campaign-assistant-enabled"
                    type="checkbox"
                    defaultChecked={settings.local_campaign_assistant_enabled}
                  />
                  <span>
                    <strong>Enable the local AI assistant</strong>
                    <small>Answers questions, creates files and prepares campaign drafts through local Ollama. No paid AI API is called.</small>
                  </span>
                </label>
                <label className="choice-row">
                  <input
                    name="protect-design-software-resources"
                    type="checkbox"
                    defaultChecked={settings.protect_design_software_resources}
                  />
                  <span>
                    <strong>Protect LightBurn and xTool resources</strong>
                    <small>Uses reduced model limits only while either design application is running; normal local performance resumes afterward.</small>
                  </span>
                </label>
                <label>
                  Local AI model
                  <select name="local-ai-model" defaultValue={settings.local_ai_model}>
                    <option value="">Use the configured default (llama3.2:3b)</option>
                    {LOCAL_AI_MODELS.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.label}
                      </option>
                    ))}
                  </select>
                  <small className="form-hint">
                    A larger model writes better outreach and follows the product knowledge more
                    closely, but needs pulling with <code>ollama pull</code> first and answers more
                    slowly. The small model is always used while LightBurn or xTool is running.
                  </small>
                </label>
                <button className="primary-action" type="submit" disabled={busy}><Save size={17} /> Save AI settings</button>
              </form>
            </section>
            <section className="form-panel settings-grid__wide" aria-labelledby="cloud-polish-heading">
              <div className="subsection-heading">
                <div><h3 id="cloud-polish-heading">Cloud draft polish</h3><p>Optional one draft at a time rewrite through Anthropic.</p></div>
                <KeyRound size={20} aria-hidden="true" />
              </div>
              <p>This sends the current draft and that lead’s details to Anthropic. Each polish costs a fraction of a penny. The key is stored in the protected credential vault and is never shown again.</p>
              <p>{cloudPolishStatus?.configured ? "An API key is saved." : "No API key is saved."}</p>
              <form className="form-grid" onSubmit={(event) => void configureCloudPolish(event)}>
                <label>Anthropic API key (leave blank to keep the saved key)
                  <input type="password" name="cloud-api-key" autoComplete="new-password" />
                </label>
                <label>Cloud model
                  <select name="cloud-polish-model" defaultValue={settings.cloud_polish_model || "claude-sonnet-5-5"}>
                    <option value="claude-sonnet-5-5">Claude Sonnet 5.5 (recommended)</option>
                    <option value="claude-haiku-5-5">Claude Haiku 5.5 (lower cost)</option>
                    {settings.cloud_polish_model === "claude-sonnet-5" ? (
                      <option value="claude-sonnet-5">Claude Sonnet 5 (previous, still saved)</option>
                    ) : null}
                    {settings.cloud_polish_model === "claude-haiku-4-5" ? (
                      <option value="claude-haiku-4-5">Claude Haiku 4.5 (previous, still saved)</option>
                    ) : null}
                  </select>
                </label>
                <label className="checkbox-row"><input type="checkbox" name="cloud-polish-enabled" defaultChecked={settings.cloud_polish_enabled} /> Enable cloud polish</label>
                <div className="form-actions">
                  <button className="primary-action" type="submit" disabled={busy}><Save size={17} /> Save cloud polish settings</button>
                  {cloudPolishStatus?.configured ? <button className="tertiary-action" type="button" disabled={busy} onClick={() => void onRemoveCloudPolish()}>Remove saved key</button> : null}
                </div>
              </form>
            </section>
            </>
            ) : null}

            {activeTask === "data" ? (
            <section className="records-panel">
              <div className="subsection-heading">
                <div><h3>Data export</h3><p>Lead details and activity history.</p></div>
                <Download size={19} aria-hidden="true" />
              </div>
              <div className="export-actions">
                <button className="secondary-action" type="button" disabled={busy} onClick={() => void onExport("json")}>
                  <Download size={17} /> Export JSON
                </button>
                <button className="secondary-action" type="button" disabled={busy} onClick={() => void onExport("csv")}>
                  <Download size={17} /> Export CSV
                </button>
              </div>
              <div className="form-notice">
                <ShieldCheck size={17} aria-hidden="true" />
                <p>CSV cells are protected against spreadsheet formula execution.</p>
              </div>
            </section>
            ) : null}

            {activeTask === "data" ? (
            <section className="form-panel">
              <div className="subsection-heading">
                <div><h3>Backup</h3><p>Create a consistent SQLite backup and checksum manifest.</p></div>
                <ArchiveRestore size={19} aria-hidden="true" />
              </div>
              <form className="form-grid" onSubmit={(event) => void createBackup(event)}>
                <label>Backup directory<input name="backup-directory" required placeholder="C:\\Users\\you\\Documents\\EtchNShine Backups" /></label>
                <button className="secondary-action" type="submit" disabled={busy}><HardDrive size={17} /> Create verified backup</button>
              </form>
              {backup ? (
                <div className="result-panel" role="status">
                  <FileCheck2 size={18} aria-hidden="true" />
                  <div><strong>Backup created</strong><p>{backup.backup_path}</p><small>SHA-256 {backup.checksum_sha256}</small></div>
                </div>
              ) : null}
              <form className="form-grid form-grid--compact" onSubmit={(event) => void verifyBackup(event)}>
                <label>Existing backup path<input name="backup-path" required placeholder="Path to .db backup" /></label>
                <button className="tertiary-action" type="submit" disabled={busy}>Verify backup</button>
              </form>
              {verification ? (
                <div className={`result-panel${verification.valid ? "" : " result-panel--error"}`} role="status">
                  <FileCheck2 size={18} aria-hidden="true" />
                  <div><strong>{verification.valid ? "Backup verified" : "Backup invalid"}</strong><p>Schema {verification.schema_version} · {humanize(verification.integrity_result)}</p></div>
                </div>
              ) : null}
            </section>
            ) : null}

            {activeTask === "about" ? (
            <>
            <section className="records-panel">
              <div className="subsection-heading">
                <div><h3>How this app protects you</h3><p>Etch ’N’ Shine Lead generation · version 0.1.0</p></div>
                <ShieldCheck size={19} aria-hidden="true" />
              </div>
              <ul className="protection-list">
                <li><ShieldCheck size={16} aria-hidden="true" />Your leads, notes and drafts stay in a database on this computer.</li>
                <li><ShieldCheck size={16} aria-hidden="true" />Nothing is sent automatically. You approve every email and send it yourself from Zoho.</li>
                <li><ShieldCheck size={16} aria-hidden="true" />A business you suppress is never contacted or added again, even if a search finds it.</li>
                <li><ShieldCheck size={16} aria-hidden="true" />Discovery only uses the connections you set up under Connections.</li>
                <li><ShieldCheck size={16} aria-hidden="true" />Exports and backups are written only where you choose, under Data and privacy.</li>
                <li><ShieldCheck size={16} aria-hidden="true" />The AI assistant runs on this computer. Cloud polish is off unless you turn it on, and then sends one draft at a time.</li>
              </ul>
            </section>
            <section className="records-panel">
              <div className="subsection-heading">
                <div><h3>Diagnostics</h3><p>Authenticated local runtime information.</p></div>
                <Database size={19} aria-hidden="true" />
              </div>
              {diagnostics ? (
                <StatGrid
                  className="diagnostics-grid"
                  wideClassName="diagnostics-grid__wide"
                  items={[
                    { label: "API", value: humanize(diagnostics.api_status) },
                    { label: "Database", value: humanize(diagnostics.database_status) },
                    { label: "Schema", value: diagnostics.schema_version },
                    { label: "Database size", value: formatBytes(diagnostics.database_size_bytes) },
                    { label: "Journal mode", value: diagnostics.journal_mode.toUpperCase() },
                    { label: "Foreign keys", value: diagnostics.foreign_keys_enabled ? "Enabled" : "Disabled" },
                    { label: "Audit events", value: diagnostics.audit_events },
                    { label: "Backups", value: diagnostics.backups },
                    { label: "Data directory", value: diagnostics.data_directory, wide: true },
                    { label: "Logs", value: diagnostics.log_directory, wide: true },
                  ]}
                />
              ) : (
                <LoadingState label="Loading diagnostics" />
              )}
            </section>
            </>
            ) : null}
          </div>
          </div>
        )}
      </section>
      </div>
    </>
  );
}
