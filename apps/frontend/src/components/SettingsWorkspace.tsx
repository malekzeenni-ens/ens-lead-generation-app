import {
  ArchiveRestore,
  AtSign,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  HardDrive,
  KeyRound,
  Save,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import type {
  BackupResult,
  Diagnostics,
  MetaConnection,
  VerificationResult,
  WorkspaceSettings,
} from "../types";
import { humanize } from "../domain";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { LoadingState, PageHeader, SectionHeading, StatGrid, TaskPanel, TaskTabs } from "./DesignSystem";

interface SettingsWorkspaceProps {
  settings: WorkspaceSettings | null;
  diagnostics: Diagnostics | null;
  metaConnection: MetaConnection | null;
  metaAuthorizationUrl: string | null;
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

export function SettingsWorkspace({
  settings,
  diagnostics,
  metaConnection,
  metaAuthorizationUrl,
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
  } = useWorkspaceActions();
  const [activeTask, setActiveTask] = useState("connections");
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

  async function selectMetaAccount(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await onSelectMetaAccount(formValue(new FormData(event.currentTarget), "meta-page-id"));
  }

  return (
    <>
      <PageHeader
        eyebrow="Local administration"
        title="Settings and diagnostics"
        description="Control local defaults, export records and verify the health of the operating core."
      />

      <TaskTabs
        id="settings-tasks"
        label="Settings tasks"
        activeId={activeTask}
        onChange={setActiveTask}
        items={[
          { id: "connections", label: "Connections" },
          { id: "defaults", label: "Defaults" },
          { id: "data", label: "Data & backup" },
          { id: "diagnostics", label: "Diagnostics" },
        ]}
      />

      <section className="workspace-section" aria-labelledby="settings-heading">
        <SectionHeading
          id="settings-heading"
          eyebrow={activeTask === "connections" ? "Provider connections" : "Workspace controls"}
          title={
            activeTask === "connections"
              ? "External connections"
              : activeTask === "defaults"
                ? "Operating defaults"
                : activeTask === "data"
                  ? "Data export and backup"
                  : "Runtime diagnostics"
          }
          description={
            activeTask === "connections"
              ? "Configure encrypted provider access without exposing credentials to the browser or database."
              : activeTask === "defaults"
                ? "Set the defaults used when creating new campaigns and dashboard follow-up windows."
                : activeTask === "data"
                  ? "Export local records and create or verify consistent backups."
                  : "Review authenticated local runtime and database health information."
          }
          icon={Settings}
        />

        {loading || !settings ? (
          <div className="records-panel"><LoadingState label="Loading settings" /></div>
        ) : (
          <TaskPanel id="settings-tasks" tabId={activeTask}>
          <div className={`settings-grid${activeTask === "data" ? "" : " settings-grid--single"}`}>
            {activeTask === "connections" ? (
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
            ) : null}

            {activeTask === "defaults" ? (
            <section className="form-panel">
              <div className="subsection-heading">
                <div><h3>Operating defaults</h3><p>Applied to new work and dashboard windows.</p></div>
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

            {activeTask === "diagnostics" ? (
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
            ) : null}
          </div>
          </TaskPanel>
        )}
      </section>
    </>
  );
}
