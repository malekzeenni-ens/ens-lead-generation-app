import { ArrowLeft, ArrowRight, Check, Megaphone, Plus, Sparkles } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";

import type { AutomationCapabilities, ProductFamily, WorkspaceSettings } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { DEFAULT_PRODUCT_CATEGORIES, formList, formValue } from "./campaignShared";
import { SectionHeading } from "./DesignSystem";

const STEPS = ["Basics", "Audience", "Discovery", "Products", "Review"] as const;

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
  const { busy, createCampaign: onCreate, planCampaignWithAssistant } = useWorkspaceActions();
  const formRef = useRef<HTMLFormElement>(null);
  const [step, setStep] = useState(0);
  const [review, setReview] = useState<{ label: string; value: string }[]>([]);
  const lastStep = STEPS.length - 1;

  /** Checks only the fields on the current step, with the browser's own messages. */
  function stepIsValid(index: number): boolean {
    const container = formRef.current?.querySelector(`[data-step="${index}"]`);
    if (!container) return true;
    const fields = container.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
      "input, select, textarea",
    );
    for (const field of fields) {
      if (!field.checkValidity()) {
        field.reportValidity();
        return false;
      }
    }
    return true;
  }

  function summarise(): void {
    if (!formRef.current) return;
    const form = new FormData(formRef.current);
    const sources = [
      form.has("campaign-google-places") && "Google Places",
      form.has("campaign-instagram") && "Instagram",
      form.has("campaign-public-registries") && "Public registries",
    ].filter(Boolean);
    const familyId = formValue(form, "campaign-product-family");
    setReview([
      { label: "Name", value: formValue(form, "campaign-name") },
      { label: "Who", value: formValue(form, "campaign-segment") },
      { label: "Where", value: `${formValue(form, "campaign-location")} · ${formValue(form, "campaign-radius")} miles` },
      { label: "Each week", value: `Up to ${formValue(form, "campaign-shortlist")} leads scoring ${formValue(form, "campaign-minimum-score")}+` },
      { label: "Keywords", value: formList(form, "campaign-keywords").join(", ") || "None" },
      { label: "Discovery", value: sources.length ? `Manual, ${sources.join(", ")}` : "Manual entry only" },
      {
        label: "Products",
        value: familyId
          ? productFamilies.find((family) => family.id === familyId)?.name ?? "Selected family"
          : formList(form, "campaign-product-categories").join(", "),
      },
    ]);
  }

  function goTo(next: number): void {
    if (next > step) {
      for (let index = step; index < next; index += 1) {
        if (!stepIsValid(index)) {
          setStep(index);
          return;
        }
      }
    }
    if (next === lastStep) summarise();
    setStep(next);
  }

  async function createCampaign(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (step < lastStep) {
      goTo(step + 1);
      return;
    }
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
      setStep(0);
      onCreated();
    }
  }

  return (
    <section className="workspace-section" aria-labelledby="campaign-heading">
      <SectionHeading
        id="campaign-heading"
        title="Create a campaign"
        description="One audience, one area, one offer."
        icon={Megaphone}
        actions={
          <button type="button" className="secondary-action" onClick={planCampaignWithAssistant}>
            <Sparkles size={16} aria-hidden="true" /> Plan with AI
          </button>
        }
      />

      <div className="section-layout section-layout--single">
        <div className="form-panel form-panel--bounded">
          <ol className="stepper" aria-label="Campaign steps">
            {STEPS.map((label, index) => (
              <li
                key={label}
                className={`stepper__step${index === step ? " stepper__step--current" : ""}${index < step ? " stepper__step--done" : ""}`}
                aria-current={index === step ? "step" : undefined}
              >
                <button type="button" onClick={() => goTo(index)} disabled={busy}>
                  <span className="stepper__number" aria-hidden="true">
                    {index < step ? <Check size={14} /> : index + 1}
                  </span>
                  {label}
                </button>
              </li>
            ))}
          </ol>
          <form
            id="campaign-form"
            ref={formRef}
            className="form-grid"
            onSubmit={(event) => void createCampaign(event)}
            onKeyDown={(event) => {
              // Enter in a field moves to the next step; only the last step creates the campaign.
              const target = event.target as HTMLElement;
              if (event.key !== "Enter" || step === lastStep || target.tagName !== "INPUT") return;
              event.preventDefault();
              goTo(step + 1);
            }}
          >
            <div className="form-step" data-step="0" hidden={step !== 0}>
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
            <label>
              Description <span className="optional-label">Optional</span>
              <textarea name="campaign-description" maxLength={2000} rows={3} />
            </label>
            </div>

            <div className="form-step" data-step="1" hidden={step !== 1}>
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
            </div>

            <div className="form-step" data-step="2" hidden={step !== 2}>
            <p className="supporting-copy">Manual entry is always on. Add the sources this campaign may search.</p>
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
            </div>

            <div className="form-step" data-step="3" hidden={step !== 3}>
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
            </div>

            <div className="form-step" data-step="4" hidden={step !== 4}>
              <dl className="campaign-review">
                {review.map((item) => (
                  <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>
                ))}
              </dl>
              <p className="supporting-copy">Stored on this computer. Runs only find and score leads; every email still waits for your approval.</p>
            </div>

            <div className="form-actions form-actions--steps">
              {step > 0 ? (
                <button className="secondary-action" type="button" disabled={busy} onClick={() => goTo(step - 1)}>
                  <ArrowLeft size={16} aria-hidden="true" /> Back
                </button>
              ) : <span />}
              {step < lastStep ? (
                <button className="primary-action" type="button" disabled={busy} onClick={() => goTo(step + 1)}>
                  Next: {STEPS[step + 1]} <ArrowRight size={16} aria-hidden="true" />
                </button>
              ) : (
                <button className="primary-action" type="submit" disabled={busy}>
                  <Plus size={18} aria-hidden="true" />
                  {busy ? "Saving…" : "Create campaign"}
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}
