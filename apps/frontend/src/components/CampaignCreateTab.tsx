import { Megaphone, Plus } from "lucide-react";
import type { FormEvent } from "react";

import type { AutomationCapabilities, ProductFamily, WorkspaceSettings } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { DEFAULT_PRODUCT_CATEGORIES, formList, formValue } from "./campaignShared";
import { SectionHeading } from "./DesignSystem";

interface CampaignCreateTabProps {
  capabilities: AutomationCapabilities | null;
  settings: WorkspaceSettings | null;
  productFamilies: ProductFamily[];
  onCreated: () => void;
}

export function CampaignCreateTab({
  capabilities,
  settings,
  productFamilies,
  onCreated,
}: CampaignCreateTabProps) {
  const { busy, createCampaign: onCreate } = useWorkspaceActions();

  async function createCampaign(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const discoverySources = ["manual"];
    if (form.has("campaign-google-places")) discoverySources.push("google_places");
    if (form.has("campaign-instagram")) discoverySources.push("instagram");
    if (form.has("campaign-public-registries")) discoverySources.push("public_registries");
    const productFamilyId = formValue(form, "campaign-product-family");
    const saved = await onCreate({
      name: formValue(form, "campaign-name"),
      description: formValue(form, "campaign-description"),
      segment: formValue(form, "campaign-segment"),
      primary_location: formValue(form, "campaign-location"),
      radius_miles: Number(formValue(form, "campaign-radius")),
      keywords: formList(form, "campaign-keywords"),
      exclusion_keywords: formList(form, "campaign-exclusions"),
      product_categories: formList(form, "campaign-product-categories"),
      product_family_id: productFamilyId || null,
      discovery_sources: discoverySources,
      weekly_shortlist_size: Number(formValue(form, "campaign-shortlist")),
      minimum_score_threshold: Number(formValue(form, "campaign-minimum-score")),
      preferred_channels: ["email", "instagram"],
      offer_settings: { digital_mock_up: true, introductory_pricing: true },
      discovery_mode: discoverySources.length > 1 ? "combined" : "manual",
    });
    if (saved) {
      formElement.reset();
      onCreated();
    }
  }

  return (
    <section className="workspace-section" aria-labelledby="campaign-heading">
      <SectionHeading
        id="campaign-heading"
        eyebrow="Controlled discovery"
        title="Create campaign"
        description="Define one audience, location, discovery approach and product-matching objective."
        icon={Megaphone}
      />

      <div className="section-layout section-layout--single">
        <div className="form-panel form-panel--bounded">
          <div className="subsection-heading">
            <div>
              <h3>New campaign</h3>
              <p>Define who to find, where to look and what to exclude.</p>
            </div>
            <span className="step-badge">01</span>
          </div>
          <form id="campaign-form" className="form-grid" onSubmit={(event) => void createCampaign(event)}>
            <label>
              Campaign name
              <input name="campaign-name" required maxLength={200} placeholder="Luton Bakery Partnerships" />
            </label>
            <label>
              Segment
              <input name="campaign-segment" required defaultValue="Bakeries and home bakers" />
            </label>
            <label>
              Primary location
              <input name="campaign-location" required defaultValue="Luton, United Kingdom" />
            </label>
            <div className="field-pair">
              <label>
                Radius
                <span className="input-with-suffix">
                  <input
                    name="campaign-radius"
                    type="number"
                    required
                    min="1"
                    max="500"
                    defaultValue={settings?.default_campaign_radius_miles ?? 25}
                  />
                  <span>miles</span>
                </span>
              </label>
              <label>
                Weekly shortlist
                <input
                  name="campaign-shortlist"
                  type="number"
                  required
                  min="1"
                  max="50"
                  defaultValue={settings?.default_weekly_shortlist_size ?? 5}
                />
              </label>
            </div>
            <label>
              Minimum shortlist score
              <span className="input-with-suffix">
                <input
                  name="campaign-minimum-score"
                  type="number"
                  required
                  min="0"
                  max="100"
                  defaultValue="50"
                  aria-label="Minimum shortlist score"
                  aria-describedby="campaign-minimum-score-hint"
                />
                <span>/100</span>
              </span>
              <small className="field-hint" id="campaign-minimum-score-hint">
                Leads below this score stay in the database but are excluded from the shortlist.
              </small>
            </label>
            <label>
              Discovery keywords
              <input
                name="campaign-keywords"
                defaultValue="bakery, cake maker, home baker"
                aria-describedby="campaign-keywords-hint"
              />
              <small className="field-hint" id="campaign-keywords-hint">
                Up to {capabilities?.maximum_queries_per_campaign ?? 3} provider searches per run.
              </small>
            </label>
            <label>
              Exclusion keywords <span className="optional-label">Optional</span>
              <input name="campaign-exclusions" placeholder="wholesaler, permanently closed" />
            </label>
            <label className="choice-row">
              <input
                name="campaign-google-places"
                type="checkbox"
                disabled={!capabilities?.google_places_configured}
              />
              <span>
                <strong>Discover with Google Places</strong>
                <small>
                  {capabilities?.google_places_configured
                    ? `Capped at ${capabilities.maximum_results_per_campaign} results per campaign run.`
                    : "Add ENS_GOOGLE_PLACES_API_KEY to the backend environment to enable this source."}
                </small>
              </span>
            </label>
            <label className="choice-row">
              <input
                name="campaign-instagram"
                type="checkbox"
                disabled={!capabilities?.instagram_connected}
              />
              <span>
                <strong>Enable Instagram profile enrichment</strong>
                <small>
                  {capabilities?.instagram_connected
                    ? `Refresh saved professional profiles through @${capabilities.instagram_account}. Add new profiles from Social leads.`
                    : "Connect a Meta Instagram professional account in Settings to enable this source."}
                </small>
              </span>
            </label>
            <label className="choice-row">
              <input
                name="campaign-public-registries"
                type="checkbox"
                disabled={!capabilities?.instagram_connected}
              />
              <span>
                <strong>Discover with public registries &amp; directories</strong>
                <small>
                  {capabilities?.instagram_connected
                    ? "Automatically checks sources relevant to this campaign's segment and keywords — e.g. the UK Food Standards Agency register for bakers, or event/wedding directories for planners. Verified through the same Meta connection as Instagram import."
                    : "Connect a Meta Instagram professional account in Settings to enable this source."}
                </small>
              </span>
            </label>
            <label>
              Product categories
              <input
                name="campaign-product-categories"
                required
                defaultValue={DEFAULT_PRODUCT_CATEGORIES.join(", ")}
                aria-label="Product categories"
                aria-describedby="campaign-product-categories-hint"
              />
              <small className="field-hint" id="campaign-product-categories-hint">
                Comma-separated values matched against Shopify Product Type or your edited catalogue category.
              </small>
            </label>
            <label>
              Product family <span className="optional-label">Optional</span>
              <select name="campaign-product-family" defaultValue="" aria-describedby="campaign-product-family-hint">
                <option value="">None — use automatic product matching</option>
                {productFamilies.map((family) => (
                  <option key={family.id} value={family.id}>{family.name}</option>
                ))}
              </select>
              <small className="field-hint" id="campaign-product-family-hint">
                When set, every lead in this campaign is matched only to this family's curated
                products instead of the automatic category/segment matching. Manage families in
                Catalogue → Product families.
              </small>
            </label>
            <label>
              Description <span className="optional-label">Optional</span>
              <textarea name="campaign-description" maxLength={2000} rows={3} />
            </label>
            <div className="form-actions">
              <p>Controlled discovery · duplicate review · local storage</p>
              <button className="primary-action" type="submit" disabled={busy}>
                <Plus size={18} aria-hidden="true" />
                {busy ? "Saving…" : "Create campaign"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}
