import { Copy, Edit3, Megaphone, Pause, Play, RefreshCw, Search } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import { usePagination } from "../pagination";
import type { AutomationCapabilities, Campaign, CampaignRun, ProductFamily } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { formList, formValue } from "./campaignShared";
import { EmptyState, LoadingState, Pagination, SectionHeading } from "./DesignSystem";
import type { CampaignUpdate } from "../api";

interface CampaignRegisterTabProps {
  campaigns: Campaign[];
  campaignRuns: CampaignRun[];
  capabilities: AutomationCapabilities | null;
  productFamilies: ProductFamily[];
}

export function CampaignRegisterTab({
  campaigns,
  campaignRuns,
  capabilities,
  productFamilies,
}: CampaignRegisterTabProps) {
  const {
    loading,
    busy,
    updateCampaign: onUpdate,
    duplicateCampaign: onDuplicate,
    runCampaign: onRunCampaign,
  } = useWorkspaceActions();
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);
  const filteredCampaigns = useMemo(() => {
    const search = query.toLocaleLowerCase();
    return campaigns.filter((campaign) =>
      [campaign.name, campaign.segment, campaign.primary_location].some((value) =>
        value.toLocaleLowerCase().includes(search),
      ),
    );
  }, [campaigns, query]);
  const campaignPages = usePagination(filteredCampaigns, 6, query);
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
    const form = new FormData(event.currentTarget);
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
      status: formValue(form, "edit-status") as CampaignUpdate["status"],
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

  return (
    <section className="workspace-section" aria-labelledby="campaign-heading">
      <SectionHeading
        id="campaign-heading"
        eyebrow="Controlled discovery"
        title="Campaign register"
        description="Search and manage local definitions without the creation form competing for attention."
        icon={Megaphone}
        count={campaigns.length}
      />

      <div className="section-layout section-layout--single">
        <div className="records-panel">
          <div className="records-heading records-heading--stackable">
            <div>
              <h3>Campaign register</h3>
              <p>Search and manage local definitions</p>
            </div>
            <label className="search-control">
              <span className="visually-hidden">Search campaigns</span>
              <Search size={16} aria-hidden="true" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search campaigns"
              />
            </label>
          </div>

          {loading ? (
            <LoadingState label="Loading campaigns" />
          ) : filteredCampaigns.length === 0 ? (
            <EmptyState
              title={campaigns.length === 0 ? "No campaigns yet" : "No campaigns match"}
              description={
                campaigns.length === 0
                  ? "Create a focused campaign to unlock manual lead entry."
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
                        {campaign.status}
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
                    <div className="record-actions">
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
                      <div className="record-actions__group" aria-label="Management actions">
                        <button
                          className="tertiary-action"
                          type="button"
                          onClick={() => setEditingId(editingId === campaign.id ? null : campaign.id)}
                        >
                          <Edit3 size={16} aria-hidden="true" /> Edit
                        </button>
                        <button
                          className="tertiary-action"
                          type="button"
                          disabled={busy || campaign.status === "inactive"}
                          onClick={() =>
                            void onUpdate(campaign.id, {
                              status: campaign.status === "active" ? "paused" : "active",
                            })
                          }
                        >
                          {campaign.status === "active" ? <Pause size={16} /> : <Play size={16} />}
                          {campaign.status === "active" ? "Pause" : "Resume"}
                        </button>
                        <button
                          className="tertiary-action"
                          type="button"
                          onClick={() =>
                            setDuplicatingId(duplicatingId === campaign.id ? null : campaign.id)
                          }
                        >
                          <Copy size={16} aria-hidden="true" /> Duplicate
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
                        <label>Status
                          <select name="edit-status" defaultValue={campaign.status}>
                            <option value="active">Active</option>
                            <option value="paused">Paused</option>
                            <option value="inactive">Inactive</option>
                          </select>
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
