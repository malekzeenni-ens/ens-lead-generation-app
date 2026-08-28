import {
  Archive,
  ArchiveRestore,
  Copy,
  Edit3,
  Megaphone,
  Pause,
  Play,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import { usePagination } from "../pagination";
import type {
  AutomationCapabilities,
  Campaign,
  CampaignRun,
  Lead,
  ProductFamily,
  Template,
} from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { formList, formValue } from "./campaignShared";
import {
  EmptyState,
  GuidanceNote,
  LoadingState,
  Pagination,
  SectionHeading,
} from "./DesignSystem";
import type { CampaignUpdate } from "../api";

interface CampaignRegisterTabProps {
  campaigns: Campaign[];
  campaignRuns: CampaignRun[];
  leads: Lead[];
  capabilities: AutomationCapabilities | null;
  productFamilies: ProductFamily[];
  templates: Template[];
}

export function CampaignRegisterTab({
  campaigns,
  campaignRuns,
  leads,
  capabilities,
  productFamilies,
  templates,
}: CampaignRegisterTabProps) {
  const {
    loading,
    busy,
    updateCampaign: onUpdate,
    duplicateCampaign: onDuplicate,
    deleteCampaign: onDelete,
    runCampaign: onRunCampaign,
  } = useWorkspaceActions();
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const archivedCount = campaigns.filter((campaign) => campaign.status === "inactive").length;
  const currentCampaignCount = campaigns.length - archivedCount;
  const filteredCampaigns = useMemo(() => {
    const search = query.toLocaleLowerCase();
    return campaigns.filter(
      (campaign) =>
        (showArchived || campaign.status !== "inactive") &&
        [campaign.name, campaign.segment, campaign.primary_location].some((value) =>
          value.toLocaleLowerCase().includes(search),
        ),
    );
  }, [campaigns, query, showArchived]);
  const campaignPages = usePagination(filteredCampaigns, 6, `${query}:${showArchived}`);
  const runningCampaignIds = new Set(
    campaignRuns
      .filter((run) => ["queued", "running"].includes(run.status))
      .map((run) => run.campaign_id),
  );

  async function updateCampaign(
    event: FormEvent<HTMLFormElement>,
    campaignId: string,
  ): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const campaign = campaigns.find((item) => item.id === campaignId);
    const keepConfiguredSource =
      capabilities?.google_places_configured === false &&
      campaign?.discovery_sources.includes("google_places");
    const useGooglePlaces = form.has("edit-google-places") || Boolean(keepConfiguredSource);
    const keepInstagramSource =
      capabilities?.instagram_connected === false &&
      campaign?.discovery_sources.includes("instagram");
    const useInstagram = form.has("edit-instagram") || Boolean(keepInstagramSource);
    const keepPublicRegistriesSource =
      capabilities?.instagram_connected === false &&
      campaign?.discovery_sources.includes("public_registries");
    const usePublicRegistries =
      form.has("edit-public-registries") || Boolean(keepPublicRegistriesSource);
    const discoverySources = ["manual"];
    if (useGooglePlaces) discoverySources.push("google_places");
    if (useInstagram) discoverySources.push("instagram");
    if (usePublicRegistries) discoverySources.push("public_registries");
    const productFamilyId = formValue(form, "edit-product-family");
    const weeklyEnabled = form.has("edit-weekly-outreach");
    const weeklyTemplateId = formValue(form, "edit-weekly-template") || null;
    const weeklyProvider = formValue(
      form,
      "edit-weekly-provider",
    ) as CampaignUpdate["weekly_outreach_provider"];
    const weeklyTemplateSelect = formElement.elements.namedItem("edit-weekly-template");
    if (weeklyTemplateSelect instanceof HTMLSelectElement) {
      weeklyTemplateSelect.setCustomValidity("");
      if (weeklyEnabled && !weeklyTemplateId) {
        weeklyTemplateSelect.setCustomValidity(
          "Choose an email template before enabling weekly outreach.",
        );
        weeklyTemplateSelect.reportValidity();
        return;
      }
    }
    const weeklyProviderSelect = formElement.elements.namedItem("edit-weekly-provider");
    if (weeklyProviderSelect instanceof HTMLSelectElement) {
      weeklyProviderSelect.setCustomValidity("");
      if (
        weeklyProvider &&
        weeklyProvider !== "scoring" &&
        !discoverySources.includes(weeklyProvider)
      ) {
        weeklyProviderSelect.setCustomValidity(
          "Enable this provider in the discovery options above before using it for the weekly refresh.",
        );
        weeklyProviderSelect.reportValidity();
        return;
      }
    }
    if (campaign && !campaign.weekly_outreach_enabled && weeklyEnabled) {
      const templateName =
        templates.find((template) => template.id === weeklyTemplateId)?.topic ??
        "the selected template";
      const providerName = (weeklyProvider ?? "scoring").replaceAll("_", " ");
      const confirmed = window.confirm(
        `Enable weekly automation for "${campaign.name}"?\n\nOn the first app opening each week, it will run ${providerName}, refresh the shortlist and prepare up to ${formValue(form, "edit-shortlist")} local drafts using ${templateName}.\n\nNo email will be sent automatically.`,
      );
      if (!confirmed) return;
    }
    const saved = await onUpdate(campaignId, {
      name: formValue(form, "edit-name"),
      description: formValue(form, "edit-description"),
      segment: formValue(form, "edit-segment"),
      primary_location: formValue(form, "edit-location"),
      radius_miles: Number(formValue(form, "edit-radius")),
      keywords: formList(form, "edit-keywords"),
      exclusion_keywords: formList(form, "edit-exclusions"),
      product_categories: formList(form, "edit-product-categories"),
      product_family_id: productFamilyId || null,
      discovery_sources: discoverySources,
      weekly_shortlist_size: Number(formValue(form, "edit-shortlist")),
      minimum_score_threshold: Number(formValue(form, "edit-minimum-score")),
      discovery_mode: discoverySources.length > 1 ? "combined" : "manual",
      weekly_outreach_enabled: weeklyEnabled,
      weekly_outreach_template_id: weeklyTemplateId,
      weekly_outreach_provider: weeklyProvider,
    });
    if (saved) setEditingId(null);
  }

  async function duplicateCampaign(
    event: FormEvent<HTMLFormElement>,
    campaignId: string,
  ): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const saved = await onDuplicate(campaignId, formValue(form, "duplicate-name"));
    if (saved) setDuplicatingId(null);
  }

  function confirmCampaignDeletion(campaign: Campaign): void {
    const associatedLeads = leads.filter((lead) => lead.campaign_ids.includes(campaign.id));
    const exclusiveLeadCount = associatedLeads.filter(
      (lead) => lead.campaign_ids.length === 1,
    ).length;
    const sharedLeadCount = associatedLeads.length - exclusiveLeadCount;
    const sharedDetail =
      sharedLeadCount > 0
        ? `\n\n${sharedLeadCount} shared lead${sharedLeadCount === 1 ? "" : "s"} will be retained in their other campaigns.`
        : "";
    const confirmed = window.confirm(
      `Delete campaign "${campaign.name}"?\n\nThis permanently deletes ${exclusiveLeadCount} lead${exclusiveLeadCount === 1 ? "" : "s"} that belong only to this campaign, including their activity, drafts and follow-ups.${sharedDetail}\n\nThis cannot be undone.`,
    );
    if (confirmed) void onDelete(campaign.id);
  }

  function confirmCampaignArchive(campaign: Campaign): void {
    const linkedLeadCount = leads.filter((lead) => lead.campaign_ids.includes(campaign.id)).length;
    const confirmed = window.confirm(
      `Archive campaign "${campaign.name}"?\n\nThis hides it from current campaigns and stops its runs and weekly automation. ${linkedLeadCount} linked lead${linkedLeadCount === 1 ? "" : "s"}, drafts and all history will be kept.\n\nYou can unarchive it later; it will return as Paused.`,
    );
    if (confirmed) void onUpdate(campaign.id, { status: "inactive" });
  }

  return (
    <section className="workspace-section" aria-labelledby="campaign-heading">
      <SectionHeading
        id="campaign-heading"
        eyebrow="Controlled discovery"
        title="Campaign register"
        description="Manage current campaigns while archived campaigns stay safely stored and out of automation."
        icon={Megaphone}
        count={currentCampaignCount}
      />

      <div className="section-layout section-layout--single">
        <div className="records-panel">
          <div className="records-heading records-heading--stackable">
            <div>
              <h3>Campaign register</h3>
              <p>Search and manage local definitions</p>
            </div>
            <div className="records-heading__actions">
              <label className="search-control">
                <span className="visually-hidden">Search campaigns</span>
                <Search size={16} aria-hidden="true" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search campaigns"
                />
              </label>
              {archivedCount > 0 ? (
                <button
                  className="tertiary-action"
                  type="button"
                  aria-pressed={showArchived}
                  onClick={() => setShowArchived((current) => !current)}
                >
                  <Archive size={16} aria-hidden="true" />
                  {showArchived ? "Hide archived" : `Show archived (${archivedCount})`}
                </button>
              ) : null}
            </div>
          </div>

          {loading ? (
            <LoadingState label="Loading campaigns" />
          ) : filteredCampaigns.length === 0 ? (
            <EmptyState
              title={
                campaigns.length === 0
                  ? "No campaigns yet"
                  : currentCampaignCount === 0 && !showArchived && !query
                    ? "No current campaigns"
                    : "No campaigns match"
              }
              description={
                campaigns.length === 0
                  ? "Create a focused campaign to unlock manual lead entry."
                  : currentCampaignCount === 0 && !showArchived && !query
                    ? `${archivedCount} archived campaign${archivedCount === 1 ? " is" : "s are"} safely stored. Use Show archived to view or restore them.`
                    : "Try a broader campaign, segment or location search."
              }
            />
          ) : (
            <>
              <div className="record-list">
              {campaignPages.items.map((campaign) => (
                <article key={campaign.id} className="campaign-record campaign-record--managed">
                  <div className="record-copy">
                    <div className="record-title-row">
                      <h3>{campaign.name}</h3>
                      <span
                        className={`status-badge${
                          campaign.status === "active"
                            ? " status-badge--success"
                            : campaign.status === "paused"
                              ? " status-badge--warning"
                              : ""
                        }`}
                      >
                        {campaign.status === "inactive"
                          ? "Archived"
                          : campaign.status === "active"
                            ? "Active"
                            : "Paused"}
                      </span>
                    </div>
                    <p>{campaign.segment}</p>
                    <dl>
                      <div><dt>Location</dt><dd>{campaign.primary_location}</dd></div>
                      <div><dt>Radius</dt><dd>{campaign.radius_miles} miles</dd></div>
                      <div><dt>Weekly</dt><dd>{campaign.weekly_shortlist_size} leads</dd></div>
                      <div><dt>Minimum score</dt><dd>{campaign.minimum_score_threshold}/100</dd></div>
                    </dl>
                    <p className="campaign-categories">
                      {campaign.product_family_id ? (
                        <>
                          <strong>Product family:</strong>{" "}
                          {productFamilies.find((family) => family.id === campaign.product_family_id)
                            ?.name ?? "Assigned family no longer exists"}
                        </>
                      ) : (
                        <>
                          <strong>Product categories:</strong>{" "}
                          {campaign.product_categories.length > 0
                            ? campaign.product_categories.join(", ")
                            : "Any segment-matched active product"}
                        </>
                      )}
                    </p>
                    <p className="campaign-categories">
                      <strong>Weekly outreach:</strong>{" "}
                      {campaign.weekly_outreach_enabled
                        ? `${templates.find((template) => template.id === campaign.weekly_outreach_template_id)?.topic ?? "Template missing"} · ${campaign.weekly_outreach_provider.replaceAll("_", " ")}${campaign.status === "inactive" ? " · stopped while archived" : ""}`
                        : "Manual only"}
                    </p>
                    <div className="record-actions">
                      {campaign.status !== "inactive" ? (
                        <div className="record-actions__group" aria-label="Execution actions">
                        {campaign.discovery_sources.includes("google_places") ? (
                          <button
                            className="secondary-action"
                            type="button"
                            disabled={
                              busy ||
                              campaign.status !== "active" ||
                              runningCampaignIds.has(campaign.id) ||
                              !capabilities?.google_places_configured
                            }
                            onClick={() => void onRunCampaign(campaign.id, "google_places")}
                          >
                            <RefreshCw size={16} aria-hidden="true" /> Run Google Places
                          </button>
                        ) : null}
                        {campaign.discovery_sources.includes("instagram") ? (
                          <button
                            className="secondary-action"
                            type="button"
                            disabled={
                              busy ||
                              campaign.status !== "active" ||
                              runningCampaignIds.has(campaign.id) ||
                              !capabilities?.instagram_connected
                            }
                            onClick={() => void onRunCampaign(campaign.id, "instagram")}
                          >
                            <RefreshCw size={16} aria-hidden="true" /> Refresh Instagram profiles
                          </button>
                        ) : null}
                        {campaign.discovery_sources.includes("public_registries") ? (
                          <button
                            className="secondary-action"
                            type="button"
                            disabled={
                              busy ||
                              campaign.status !== "active" ||
                              runningCampaignIds.has(campaign.id) ||
                              !capabilities?.instagram_connected
                            }
                            onClick={() => void onRunCampaign(campaign.id, "public_registries")}
                          >
                            <RefreshCw size={16} aria-hidden="true" /> Run public registries
                          </button>
                        ) : null}
                        <button
                          className="secondary-action"
                          type="button"
                          disabled={
                            busy || campaign.status !== "active" || runningCampaignIds.has(campaign.id)
                          }
                          onClick={() => void onRunCampaign(campaign.id, "scoring")}
                        >
                          <RefreshCw size={16} aria-hidden="true" />
                          {runningCampaignIds.has(campaign.id)
                            ? "Run in progress"
                            : "Refresh scoring only"}
                        </button>
                        </div>
                      ) : null}
                      <div className="record-actions__group" aria-label="Management actions">
                        <button
                          className="tertiary-action"
                          type="button"
                          onClick={() => setEditingId(editingId === campaign.id ? null : campaign.id)}
                        >
                          <Edit3 size={16} aria-hidden="true" /> Edit
                        </button>
                        {campaign.status === "inactive" ? (
                          <button
                            className="tertiary-action"
                            type="button"
                            disabled={busy}
                            title="Restore this campaign as Paused so you can review it before restarting"
                            onClick={() => void onUpdate(campaign.id, { status: "paused" })}
                          >
                            <ArchiveRestore size={16} aria-hidden="true" /> Unarchive
                          </button>
                        ) : (
                          <>
                            <button
                              className="tertiary-action"
                              type="button"
                              disabled={busy}
                              onClick={() =>
                                void onUpdate(campaign.id, {
                                  status: campaign.status === "active" ? "paused" : "active",
                                })
                              }
                            >
                              {campaign.status === "active" ? (
                                <Pause size={16} aria-hidden="true" />
                              ) : (
                                <Play size={16} aria-hidden="true" />
                              )}
                              {campaign.status === "active" ? "Pause" : "Resume"}
                            </button>
                            <button
                              className="tertiary-action"
                              type="button"
                              disabled={busy || runningCampaignIds.has(campaign.id)}
                              title={
                                runningCampaignIds.has(campaign.id)
                                  ? "Wait for the active run to finish or cancel it before archiving"
                                  : "Hide this campaign and stop its automation without deleting anything"
                              }
                              onClick={() => confirmCampaignArchive(campaign)}
                            >
                              <Archive size={16} aria-hidden="true" /> Archive
                            </button>
                          </>
                        )}
                        <button
                          className="tertiary-action"
                          type="button"
                          onClick={() =>
                            setDuplicatingId(duplicatingId === campaign.id ? null : campaign.id)
                          }
                        >
                          <Copy size={16} aria-hidden="true" /> Duplicate
                        </button>
                        <button
                          className="danger-action"
                          type="button"
                          disabled={busy || runningCampaignIds.has(campaign.id)}
                          title={
                            runningCampaignIds.has(campaign.id)
                              ? "Wait for the active run to finish or cancel it before deletion"
                              : "Permanently delete this campaign and its exclusively linked leads"
                          }
                          onClick={() => confirmCampaignDeletion(campaign)}
                        >
                          <Trash2 size={16} aria-hidden="true" /> Delete campaign
                        </button>
                      </div>
                    </div>

                    {editingId === campaign.id ? (
                      <form
                        className="inline-editor inline-editor--capped"
                        onSubmit={(event) => void updateCampaign(event, campaign.id)}
                      >
                        <label>Name<input name="edit-name" defaultValue={campaign.name} required /></label>
                        <label>Segment<input name="edit-segment" defaultValue={campaign.segment} required /></label>
                        <label>Location<input name="edit-location" defaultValue={campaign.primary_location} required /></label>
                        <div className="field-pair">
                          <label>Radius<input name="edit-radius" type="number" min="1" max="500" defaultValue={campaign.radius_miles} required /></label>
                          <label>Weekly<input name="edit-shortlist" type="number" min="1" max="50" defaultValue={campaign.weekly_shortlist_size} required /></label>
                        </div>
                        <label>
                          Minimum shortlist score
                          <span className="input-with-suffix">
                            <input
                              name="edit-minimum-score"
                              type="number"
                              min="0"
                              max="100"
                              defaultValue={campaign.minimum_score_threshold}
                              aria-label="Minimum shortlist score"
                              required
                            />
                            <span>/100</span>
                          </span>
                        </label>
                        <label>
                          Discovery keywords
                          <input
                            name="edit-keywords"
                            defaultValue={campaign.keywords.join(", ")}
                          />
                        </label>
                        <label>
                          Exclusion keywords
                          <input
                            name="edit-exclusions"
                            defaultValue={campaign.exclusion_keywords.join(", ")}
                          />
                        </label>
                        <label className="choice-row">
                          <input
                            name="edit-google-places"
                            type="checkbox"
                            defaultChecked={campaign.discovery_sources.includes("google_places")}
                            disabled={!capabilities?.google_places_configured}
                          />
                          <span>
                            <strong>Discover with Google Places</strong>
                            <small>
                              {capabilities?.google_places_configured
                                ? "Run controlled area and keyword searches before scoring."
                                : "Provider key is not configured; the existing source setting is preserved."}
                            </small>
                          </span>
                        </label>
                        <label className="choice-row">
                          <input
                            name="edit-instagram"
                            type="checkbox"
                            defaultChecked={campaign.discovery_sources.includes("instagram")}
                            disabled={!capabilities?.instagram_connected}
                          />
                          <span>
                            <strong>Enable Instagram profile enrichment</strong>
                            <small>
                              {capabilities?.instagram_connected
                                ? `Refresh saved professional profiles through @${capabilities.instagram_account}. Add new profiles from Social leads.`
                                : "Meta is not connected; the existing source setting is preserved."}
                            </small>
                          </span>
                        </label>
                        <label className="choice-row">
                          <input
                            name="edit-public-registries"
                            type="checkbox"
                            defaultChecked={campaign.discovery_sources.includes("public_registries")}
                            disabled={!capabilities?.instagram_connected}
                          />
                          <span>
                            <strong>Discover with public registries &amp; directories</strong>
                            <small>
                              {capabilities?.instagram_connected
                                ? "Automatically checks sources relevant to this campaign's segment and keywords, verified through the same Meta connection."
                                : "Meta is not connected; the existing source setting is preserved."}
                            </small>
                          </span>
                        </label>
                        <label>
                          Product categories
                          <input
                            name="edit-product-categories"
                            defaultValue={campaign.product_categories.join(", ")}
                            aria-label="Product categories"
                            required
                          />
                          <small className="field-hint">
                            Use the category names shown in the product catalogue.
                          </small>
                        </label>
                        <label>
                          Product family <span className="optional-label">Optional</span>
                          <select name="edit-product-family" defaultValue={campaign.product_family_id ?? ""}>
                            <option value="">None — use automatic product matching</option>
                            {productFamilies.map((family) => (
                              <option key={family.id} value={family.id}>{family.name}</option>
                            ))}
                          </select>
                        </label>
                        <div className="subsection-heading subsection-heading--compact">
                          <div>
                            <h3>Weekly outreach</h3>
                            <p>
                              On the first app opening of each week, prepare drafts from this
                              campaign&apos;s strongest contact-ready leads.
                            </p>
                          </div>
                        </div>
                        <GuidanceNote title="Before you enable weekly outreach">
                          Enabling this campaign authorises a current-week refresh when the app
                          first opens, or when you manually run due campaigns. It prepares local
                          drafts only; review, approval and sending remain your decisions.
                        </GuidanceNote>
                        <label className="choice-row">
                          <input
                            name="edit-weekly-outreach"
                            type="checkbox"
                            defaultChecked={campaign.weekly_outreach_enabled}
                            disabled={templates.length === 0}
                          />
                          <span>
                            <strong>Prepare outreach automatically each week</strong>
                            <small>Drafts still require your review and approval before Zoho opens.</small>
                          </span>
                        </label>
                        <label>
                          Weekly email template
                          <select
                            name="edit-weekly-template"
                            defaultValue={campaign.weekly_outreach_template_id ?? ""}
                          >
                            <option value="">Choose a template</option>
                            {templates.map((template) => (
                              <option key={template.id} value={template.id}>{template.topic}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Weekly refresh
                          <select
                            name="edit-weekly-provider"
                            defaultValue={campaign.weekly_outreach_provider}
                          >
                            <option value="scoring">Existing leads · refresh scores only</option>
                            <option value="google_places">Google Places, then score</option>
                            <option value="instagram">Instagram profiles, then score</option>
                            <option value="public_registries">Public registries, then score</option>
                          </select>
                          <small className="field-hint">
                            External providers must also be enabled above. Campaign capacity stays
                            at {campaign.weekly_shortlist_size} leads.
                          </small>
                        </label>
                        <label>Description<textarea name="edit-description" rows={2} defaultValue={campaign.description ?? ""} /></label>
                        <button className="primary-action" type="submit" disabled={busy}>Save campaign</button>
                      </form>
                    ) : null}

                    {duplicatingId === campaign.id ? (
                      <form
                        className="inline-editor inline-editor--row"
                        onSubmit={(event) => void duplicateCampaign(event, campaign.id)}
                      >
                        <label>
                          New campaign name
                          <input name="duplicate-name" defaultValue={`${campaign.name} copy`} required />
                        </label>
                        <button className="primary-action" type="submit" disabled={busy}>
                          Create paused copy
                        </button>
                      </form>
                    ) : null}
                  </div>
                </article>
              ))}
              </div>
              <Pagination
                page={campaignPages.page}
                pageCount={campaignPages.pageCount}
                pageSize={campaignPages.pageSize}
                totalItems={campaignPages.totalItems}
                itemLabel="campaigns"
                onPageChange={campaignPages.setPage}
              />
            </>
          )}
        </div>
      </div>
    </section>
  );
}
