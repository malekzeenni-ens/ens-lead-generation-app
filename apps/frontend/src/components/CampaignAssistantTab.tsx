import {
  Bot,
  CheckCircle2,
  Cpu,
  Plus,
  Save,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api";
import type {
  AutomationCapabilities,
  AssistantContextSelection,
  Campaign,
  CampaignAssistantStatus,
  CampaignDraft,
  CampaignDraftCampaign,
  Lead,
  OutreachBatch,
  ProductFamily,
  Shortlist,
} from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { formList, formValue } from "./campaignShared";
import { LoadingState, SectionHeading } from "./DesignSystem";
import { GeneralAssistantPanel } from "./GeneralAssistantPanel";

interface CampaignAssistantTabProps {
  capabilities: AutomationCapabilities | null;
  productFamilies: ProductFamily[];
  onApproved: () => void;
  campaigns: Campaign[];
  leads: Lead[];
  batches: OutreachBatch[];
  shortlists: Shortlist[];
  initialContext: AssistantContextSelection;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.details.message;
  return error instanceof Error ? error.message : "The local assistant could not complete that request.";
}

function displayValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function CampaignAssistantTab({
  capabilities,
  productFamilies,
  onApproved,
  campaigns,
  leads,
  batches,
  shortlists,
  initialContext,
}: CampaignAssistantTabProps) {
  const { busy: workspaceBusy, approveCampaignDraft } = useWorkspaceActions();
  const [status, setStatus] = useState<CampaignAssistantStatus | null>(null);
  const [draft, setDraft] = useState<CampaignDraft | null>(null);
  const [instruction, setInstruction] = useState("");
  const [assistantMode, setAssistantMode] = useState<"general" | "campaign">("general");
  const [working, setWorking] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refreshStatus(): Promise<void> {
    try {
      setStatus(await api.campaignAssistantStatus());
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  useEffect(() => {
    let active = true;
    void Promise.all([api.campaignAssistantStatus(), api.campaignDrafts()])
      .then(([currentStatus, drafts]) => {
        if (!active) return;
        setStatus(currentStatus);
        setDraft(
          drafts.find((item) => !["approved", "discarded"].includes(item.status)) ?? null,
        );
      })
      .catch((caught: unknown) => {
        if (active) setError(errorMessage(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const pendingOverride = useMemo(
    () => draft?.overrides.find((item) => item.status === "pending") ?? null,
    [draft],
  );

  async function submitInstruction(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const message = instruction.trim();
    if (!message || working || !status?.ready) return;
    setWorking(true);
    setError(null);
    try {
      const next = draft
        ? await api.sendCampaignDraftMessage(draft.id, message, draft.version)
        : await api.createCampaignDraft(message);
      setDraft(next);
      setInstruction("");
      await refreshStatus();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function decideOverride(decision: "confirm" | "reject"): Promise<void> {
    if (!draft || !pendingOverride || working) return;
    setWorking(true);
    setError(null);
    try {
      setDraft(
        await api.decideCampaignDraftOverride(
          draft.id,
          pendingOverride.id,
          decision,
          draft.version,
        ),
      );
      await refreshStatus();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function saveDraft(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!draft?.campaign || working) return;
    const form = new FormData(event.currentTarget);
    const discoverySources = ["manual"];
    if (form.has("assistant-google-places")) discoverySources.push("google_places");
    if (form.has("assistant-instagram")) discoverySources.push("instagram");
    if (form.has("assistant-public-registries")) discoverySources.push("public_registries");
    const preferredChannels: string[] = [];
    if (form.has("assistant-email")) preferredChannels.push("email");
    if (form.has("assistant-instagram-channel")) preferredChannels.push("instagram");
    const familyId = formValue(form, "assistant-product-family");
    const changes: Partial<CampaignDraftCampaign> = {
      name: formValue(form, "assistant-name"),
      description: formValue(form, "assistant-description") || null,
      segment: formValue(form, "assistant-segment"),
      primary_location: formValue(form, "assistant-location"),
      radius_miles: Number(formValue(form, "assistant-radius")),
      keywords: formList(form, "assistant-keywords"),
      exclusion_keywords: formList(form, "assistant-exclusions"),
      product_categories: formList(form, "assistant-product-categories"),
      product_family_id: familyId || null,
      discovery_sources: discoverySources,
      weekly_shortlist_size: Number(formValue(form, "assistant-shortlist")),
      minimum_score_threshold: Number(formValue(form, "assistant-minimum-score")),
      preferred_channels: preferredChannels,
      offer_settings: {
        digital_mock_up: form.has("assistant-mock-up"),
        introductory_pricing: form.has("assistant-introductory-pricing"),
      },
      discovery_mode: discoverySources.length > 1 ? "combined" : "manual",
    };
    setWorking(true);
    setError(null);
    try {
      setDraft(await api.updateCampaignDraft(draft.id, changes, draft.version));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function approve(): Promise<void> {
    if (!draft || draft.status !== "ready" || working || workspaceBusy) return;
    setWorking(true);
    setError(null);
    const result = await approveCampaignDraft(draft.id, draft.version);
    setWorking(false);
    if (result) {
      setDraft(result.draft);
      onApproved();
    }
  }

  async function discard(): Promise<void> {
    if (!draft || working) return;
    setWorking(true);
    setError(null);
    try {
      await api.discardCampaignDraft(draft.id, draft.version);
      setDraft(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <LoadingState label="Loading local AI assistant" />;

  return (
    <section className="workspace-section" aria-labelledby="campaign-assistant-heading">
      <SectionHeading
        id="campaign-assistant-heading"
        eyebrow="Private local AI"
        title="Ask, plan and create with Llama 3.2"
        description="Ask about this app and its live local workspace, create useful working documents, or prepare a paused campaign draft."
        icon={Sparkles}
      />

      <div className="assistant-status" role="status">
        <Cpu size={18} aria-hidden="true" />
        <div>
          <strong>{status?.model ?? "llama3.2:3b"}</strong>
          <p>{status?.message ?? "Assistant status unavailable."}</p>
        </div>
        <span
          className={`status-badge${status?.ready ? " status-badge--success" : " status-badge--warning"}`}
        >
          {status?.resource_profile === "design_software" ? "Reduced resources" : status?.ready ? "Ready" : "Setup needed"}
        </span>
      </div>

      {!status?.ready ? (
        <div className="form-notice assistant-setup" role="note">
          <ShieldAlert size={18} aria-hidden="true" />
          <div>
            <strong>Local setup required</strong>
            <p>Install and start Ollama, then run <code>ollama pull llama3.2:3b</code>. No paid AI API is used.</p>
          </div>
        </div>
      ) : null}

      {error ? <div className="alert alert--error" role="alert"><ShieldAlert size={18} />{error}</div> : null}

      <div className="assistant-mode-toggle" role="tablist" aria-label="Local assistant mode">
        <button
          type="button"
          role="tab"
          aria-selected={assistantMode === "general"}
          className={assistantMode === "general" ? "is-active" : ""}
          onClick={() => setAssistantMode("general")}
        >
          App copilot
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={assistantMode === "campaign"}
          className={assistantMode === "campaign" ? "is-active" : ""}
          onClick={() => setAssistantMode("campaign")}
        >
          Campaign draft{draft ? ` · ${draft.status.replaceAll("_", " ")}` : ""}
        </button>
      </div>

      <div className="campaign-assistant-layout">
        {assistantMode === "general" ? (
          <GeneralAssistantPanel
            ready={Boolean(status?.ready)}
            working={working}
            setWorking={setWorking}
            campaigns={campaigns}
            leads={leads}
            batches={batches}
            shortlists={shortlists}
            initialContext={initialContext}
            onCampaignDraft={(nextDraft) => {
              setDraft(nextDraft);
              setAssistantMode("campaign");
            }}
          />
        ) : (
        <section className="records-panel assistant-chat" aria-label="Campaign assistant conversation">
          <div className="subsection-heading">
            <div>
              <h3>Campaign brief</h3>
              <p>The model follows the campaign playbook unless you explicitly confirm an override.</p>
            </div>
            <Bot size={20} aria-hidden="true" />
          </div>

          <div className="assistant-thread" aria-live="polite">
            {!draft ? (
              <div className="assistant-empty">
                <Sparkles size={22} aria-hidden="true" />
                <p>Try: “Create a baking campaign for Luton.”</p>
              </div>
            ) : (
              draft.revisions.map((revision) => (
                <div className="assistant-exchange" key={revision.id}>
                  {revision.user_instruction ? (
                    <div className="assistant-message assistant-message--user">
                      <span>You</span>
                      <p>{revision.user_instruction}</p>
                    </div>
                  ) : null}
                  <div className="assistant-message assistant-message--model">
                    <span>Local planner</span>
                    <p>{revision.assistant_message}</p>
                    {revision.questions.length > 0 ? (
                      <ul>{revision.questions.map((question) => <li key={question}>{question}</li>)}</ul>
                    ) : null}
                  </div>
                </div>
              ))
            )}
            {working ? <div className="assistant-thinking"><span /> Preparing locally…</div> : null}
          </div>

          {pendingOverride && draft ? (
            <div className="override-card" role="alert">
              <div className="override-card__heading">
                <ShieldAlert size={19} aria-hidden="true" />
                <div><strong>Playbook override requested</strong><p>{pendingOverride.summary}</p></div>
              </div>
              <div className="override-items">
                {pendingOverride.items.map((item) => (
                  <article key={item.item_id}>
                    <strong>{item.field.replaceAll("_", " ")}</strong>
                    <p><span>Playbook:</span> {displayValue(item.playbook_recommendation)}</p>
                    <p><span>Your request:</span> {displayValue(item.requested_value)}</p>
                    <small>{item.impact}</small>
                  </article>
                ))}
              </div>
              <div className="override-actions">
                <button className="primary-action" type="button" disabled={working} onClick={() => void decideOverride("confirm")}>
                  <CheckCircle2 size={17} /> Confirm override
                </button>
                <button className="tertiary-action" type="button" disabled={working} onClick={() => void decideOverride("reject")}>
                  Keep playbook recommendation
                </button>
              </div>
            </div>
          ) : null}

          <form className="assistant-composer" onSubmit={(event) => void submitInstruction(event)}>
            <label htmlFor="assistant-instruction" className="visually-hidden">Campaign instruction</label>
            <textarea
              id="assistant-instruction"
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              rows={3}
              maxLength={2000}
              disabled={!status?.ready || working || draft?.status === "awaiting_override_confirmation"}
              placeholder={draft ? "Ask for a change to this draft…" : "Create a baking campaign for Luton…"}
            />
            <button className="primary-action" type="submit" disabled={!instruction.trim() || !status?.ready || working || draft?.status === "awaiting_override_confirmation"}>
              <Send size={17} /> {draft ? "Send change" : "Create draft"}
            </button>
          </form>
        </section>
        )}

        <section className="form-panel assistant-review" aria-label="Campaign draft review">
          <div className="subsection-heading">
            <div><h3>Review draft</h3><p>Nothing is created or run until you approve this paused draft.</p></div>
            {draft ? <span className="status-badge">{draft.status.replaceAll("_", " ")}</span> : <span className="step-badge">02</span>}
          </div>

          {!draft?.campaign ? (
            <div className="assistant-empty assistant-empty--review">
              <CheckCircle2 size={24} aria-hidden="true" />
              <p>The complete, editable campaign will appear here after the brief and any overrides are resolved.</p>
            </div>
          ) : (
            <form key={`${draft.id}-${draft.version}`} className="form-grid" onSubmit={(event) => void saveDraft(event)}>
              <label>Campaign name<input name="assistant-name" required maxLength={200} defaultValue={draft.campaign.name} /></label>
              <label>Segment<input name="assistant-segment" required maxLength={100} defaultValue={draft.campaign.segment} /></label>
              <label>Primary location<input name="assistant-location" required maxLength={200} defaultValue={draft.campaign.primary_location} /></label>
              <div className="field-pair">
                <label>Radius<span className="input-with-suffix"><input name="assistant-radius" type="number" min="1" max="500" required defaultValue={draft.campaign.radius_miles} /><span>miles</span></span></label>
                <label>Weekly shortlist<input name="assistant-shortlist" type="number" min="1" max="50" required defaultValue={draft.campaign.weekly_shortlist_size} /></label>
              </div>
              <label>Minimum shortlist score<span className="input-with-suffix"><input name="assistant-minimum-score" type="number" min="0" max="100" required defaultValue={draft.campaign.minimum_score_threshold} /><span>/100</span></span></label>
              <label>Discovery keywords<input name="assistant-keywords" defaultValue={draft.campaign.keywords.join(", ")} /></label>
              <label>Exclusion keywords<input name="assistant-exclusions" defaultValue={draft.campaign.exclusion_keywords.join(", ")} /></label>
              <label>Product categories<input name="assistant-product-categories" defaultValue={draft.campaign.product_categories.join(", ")} /></label>
              <label>Product family<select name="assistant-product-family" defaultValue={draft.campaign.product_family_id ?? ""}><option value="">None — automatic matching</option>{productFamilies.map((family) => <option key={family.id} value={family.id}>{family.name}</option>)}</select></label>

              <fieldset className="assistant-options"><legend>Discovery sources</legend>
                <label className="choice-row"><input type="checkbox" checked disabled /><span><strong>Manual</strong><small>Always available as the safe baseline.</small></span></label>
                <label className="choice-row"><input name="assistant-google-places" type="checkbox" defaultChecked={draft.campaign.discovery_sources.includes("google_places")} disabled={!capabilities?.google_places_configured} /><span><strong>Google Places</strong><small>May incur provider usage charges when the campaign is run.</small></span></label>
                <label className="choice-row"><input name="assistant-instagram" type="checkbox" defaultChecked={draft.campaign.discovery_sources.includes("instagram")} disabled={!capabilities?.instagram_connected} /><span><strong>Instagram</strong><small>Available when Meta is connected.</small></span></label>
                <label className="choice-row"><input name="assistant-public-registries" type="checkbox" defaultChecked={draft.campaign.discovery_sources.includes("public_registries")} /><span><strong>Public registries</strong><small>Uses the configured local directory workflow.</small></span></label>
              </fieldset>

              <fieldset className="assistant-options"><legend>Outreach and offer</legend>
                <label className="choice-row"><input name="assistant-email" type="checkbox" defaultChecked={draft.campaign.preferred_channels.includes("email")} /><span><strong>Email</strong></span></label>
                <label className="choice-row"><input name="assistant-instagram-channel" type="checkbox" defaultChecked={draft.campaign.preferred_channels.includes("instagram")} /><span><strong>Instagram</strong></span></label>
                <label className="choice-row"><input name="assistant-mock-up" type="checkbox" defaultChecked={Boolean(draft.campaign.offer_settings.digital_mock_up)} /><span><strong>Digital mock-up</strong></span></label>
                <label className="choice-row"><input name="assistant-introductory-pricing" type="checkbox" defaultChecked={Boolean(draft.campaign.offer_settings.introductory_pricing)} /><span><strong>Introductory pricing</strong></span></label>
              </fieldset>

              <label>Description<textarea name="assistant-description" maxLength={2000} rows={3} defaultValue={draft.campaign.description ?? ""} /></label>

              {draft.assumptions.length > 0 || draft.warnings.length > 0 ? (
                <div className="assistant-notes">
                  {draft.assumptions.map((item) => <p key={item}><strong>Assumption:</strong> {item}</p>)}
                  {draft.warnings.map((item) => <p key={item}><strong>Warning:</strong> {item}</p>)}
                </div>
              ) : null}

              <div className="assistant-review-actions">
                <button className="secondary-action" type="submit" disabled={working || workspaceBusy}><Save size={17} /> Save edits</button>
                <button className="primary-action" type="button" disabled={working || workspaceBusy || draft.status !== "ready"} onClick={() => void approve()}><CheckCircle2 size={17} /> Approve paused campaign</button>
              </div>
            </form>
          )}

          {draft && !["approved", "discarded"].includes(draft.status) ? (
            <div className="assistant-draft-footer">
              <button className="danger-action" type="button" disabled={working} onClick={() => void discard()}><Trash2 size={16} /> Discard draft</button>
              <button className="tertiary-action" type="button" disabled={working} onClick={() => setDraft(null)}><Plus size={16} /> Start another brief</button>
            </div>
          ) : null}
        </section>
      </div>
    </section>
  );
}
