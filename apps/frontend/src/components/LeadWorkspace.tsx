import { AlertTriangle, ArrowRight, Plus, Search, UserRoundSearch } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import { PIPELINE_STAGES, humanize } from "../domain";
import { usePagination } from "../pagination";
import type { Campaign, Lead } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import {
  EmptyState,
  LoadingState,
  PageHeader,
  Pagination,
  SectionHeading,
  TaskPanel,
  TaskTabs,
} from "./DesignSystem";

interface LeadWorkspaceProps {
  campaigns: Campaign[];
  leads: Lead[];
  initialClassificationFilter?: "" | "review";
}

function formValue(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

const SOURCE_LABELS: Record<string, string> = {
  google: "Google Places",
  instagram: "Instagram",
  facebook: "Facebook",
  manual: "Manual",
  unknown: "Unknown",
  fhrs: "FHRS register",
  event_directory: "Event directory",
  public_registries: "Public registries",
};
const PRIMARY_SOURCE_TYPES = ["google", "instagram", "facebook", "manual"];

function leadSourceTypes(lead: Lead): string[] {
  const sourceTypes = [
    ...new Set(
      lead.sources
        .map((source) => source.source_type.trim().toLocaleLowerCase())
        .filter((sourceType) => sourceType && sourceType !== "website"),
    ),
  ];
  return sourceTypes.length ? sourceTypes : ["unknown"];
}

function sourceLabel(sourceType: string): string {
  return SOURCE_LABELS[sourceType] ?? humanize(sourceType);
}

export function LeadWorkspace({
  campaigns,
  leads,
  initialClassificationFilter = "",
}: LeadWorkspaceProps) {
  const {
    loading,
    busy,
    createLead: onCreate,
    manageLead: onManage,
  } = useWorkspaceActions();
  const [activeTask, setActiveTask] = useState("browse");
  const [query, setQuery] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [stage, setStage] = useState("");
  const [suppression, setSuppression] = useState("all");
  const [reviewFilter, setReviewFilter] = useState(initialClassificationFilter);
  const sourceOptions = useMemo(
    () => {
      const discoveredTypes = new Set(leads.flatMap(leadSourceTypes));
      const additionalTypes = [...discoveredTypes]
        .filter((value) => !PRIMARY_SOURCE_TYPES.includes(value) && value !== "unknown")
        .sort((left, right) => sourceLabel(left).localeCompare(sourceLabel(right)));
      return [...PRIMARY_SOURCE_TYPES, ...additionalTypes];
    },
    [leads],
  );
  const filteredLeads = useMemo(() => {
    const search = query.toLocaleLowerCase();
    return leads.filter((lead) => {
      const matchesSearch = [
        lead.business_name,
        lead.segment,
        lead.location,
        lead.phone_number ?? "",
        lead.public_email ?? "",
        ...leadSourceTypes(lead).map(sourceLabel),
      ].some((value) => value.toLocaleLowerCase().includes(search));
      const matchesCampaign = !campaignId || lead.campaign_ids.includes(campaignId);
      const matchesSource = !sourceType || leadSourceTypes(lead).includes(sourceType);
      const matchesStage = !stage || lead.pipeline_stage === stage;
      const matchesSuppression =
        suppression === "all" || lead.suppressed === (suppression === "suppressed");
      const matchesReview =
        !reviewFilter || (reviewFilter === "review") === (lead.contact_classification === "unknown");
      return (
        matchesSearch &&
        matchesCampaign &&
        matchesSource &&
        matchesStage &&
        matchesSuppression &&
        matchesReview
      );
    });
  }, [campaignId, leads, query, reviewFilter, sourceType, stage, suppression]);
  const leadPages = usePagination(
    filteredLeads,
    10,
    `${query}|${campaignId}|${sourceType}|${stage}|${suppression}|${reviewFilter}`,
  );

  async function createLead(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const website = formValue(form, "lead-website");
    const instagramUrl = formValue(form, "lead-instagram");
    const facebookUrl = formValue(form, "lead-facebook");
    const phoneNumber = formValue(form, "lead-phone");
    const publicEmail = formValue(form, "lead-email");
    const saved = await onCreate({
      campaign_id: formValue(form, "lead-campaign"),
      business_name: formValue(form, "lead-name"),
      segment: formValue(form, "lead-segment"),
      location: formValue(form, "lead-location"),
      ...(website ? { website } : {}),
      ...(instagramUrl ? { instagram_url: instagramUrl } : {}),
      ...(facebookUrl ? { facebook_url: facebookUrl } : {}),
      ...(phoneNumber ? { phone_number: phoneNumber } : {}),
      ...(publicEmail ? { public_email: publicEmail } : {}),
      contact_classification: formValue(form, "lead-classification") || "unknown",
      source: {
        name: "Manual entry",
        source_type: "manual",
        ...(website || instagramUrl || facebookUrl
          ? { source_url: website || instagramUrl || facebookUrl }
          : {}),
        classification: "user_verified",
      },
    });
    if (saved) {
      formElement.reset();
      setActiveTask("browse");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Prospect register"
        title="All leads"
        description="Capture public business evidence, search the register and open any lead for action."
      />

      <TaskTabs
        id="leads-tasks"
        label="Lead tasks"
        activeId={activeTask}
        onChange={setActiveTask}
        items={[
          { id: "browse", label: "Browse leads", count: leads.length },
          { id: "add", label: "Add lead" },
        ]}
      />

      <section className="workspace-section" aria-labelledby="lead-heading">
        <SectionHeading
          id="lead-heading"
          eyebrow={activeTask === "add" ? "Evidence-backed entry" : "Prospect register"}
          title={activeTask === "add" ? "Add manual lead" : "Browse leads"}
          description={
            activeTask === "add"
              ? "Capture one public business source and assign the lead to a campaign."
              : "Search, filter and open a lead without unrelated entry controls."
          }
          icon={UserRoundSearch}
          count={activeTask === "browse" ? leads.length : undefined}
        />

        {activeTask === "add" ? (
          <TaskPanel id="leads-tasks" tabId="add">
          <div className="form-panel">
            <div className="subsection-heading">
              <div>
                <h3>Add manual lead</h3>
                <p>A website, Instagram profile or Facebook page is required.</p>
              </div>
              <span className="step-badge">02</span>
            </div>
            <form className="form-grid" onSubmit={(event) => void createLead(event)}>
              <label>
                Campaign
                <select name="lead-campaign" required disabled={campaigns.length === 0}>
                  <option value="">Select a campaign</option>
                  {campaigns.map((campaign) => (
                    <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
                  ))}
                </select>
              </label>
              <div className="field-pair">
                <label>Business name<input name="lead-name" required maxLength={200} /></label>
                <label>Location<input name="lead-location" required placeholder="Luton" /></label>
              </div>
              <label>Segment<input name="lead-segment" required defaultValue="Bakeries and home bakers" /></label>
              <div className="field-pair">
                <label>
                  Website <span className="optional-label">One required</span>
                  <input name="lead-website" type="url" placeholder="https://example.test" />
                </label>
                <label>Public phone <span className="optional-label">Optional</span><input name="lead-phone" type="tel" maxLength={100} /></label>
              </div>
              <div className="field-pair">
                <label>Instagram profile <span className="optional-label">One required</span><input name="lead-instagram" type="url" placeholder="https://instagram.com/example" /></label>
                <label>Facebook page <span className="optional-label">One required</span><input name="lead-facebook" type="url" placeholder="https://facebook.com/example" /></label>
              </div>
              <label>Public email <span className="optional-label">Optional</span><input name="lead-email" type="email" maxLength={320} /></label>
              <label>
                Contact classification
                <select name="lead-classification" defaultValue="unknown">
                  <option value="unknown">Unknown — review required</option>
                  <option value="corporate_subscriber">Corporate subscriber</option>
                  <option value="sole_trader_or_individual">Sole trader / individual</option>
                  <option value="partnership_individual_treatment">Partnership requiring review</option>
                </select>
              </label>
              <div className="form-notice">
                <AlertTriangle size={17} aria-hidden="true" />
                <p>Manual entry records evidence; it does not approve or send outreach.</p>
              </div>
              <div className="form-actions">
                <p>Source: manual entry · classification: user verified</p>
                <button
                  className="primary-action"
                  type="submit"
                  disabled={busy || campaigns.length === 0}
                >
                  <Plus size={18} aria-hidden="true" />
                  {busy ? "Saving…" : "Add lead with source"}
                </button>
              </div>
            </form>
          </div>
          </TaskPanel>
        ) : (
          <TaskPanel id="leads-tasks" tabId="browse">
          <div className="records-panel records-panel--table">
            <div className="filter-bar filter-bar--leads" aria-label="Lead filters">
              <label className="search-control">
                <span className="visually-hidden">Search leads</span>
                <Search size={16} aria-hidden="true" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search leads" />
              </label>
              <label>
                <span className="visually-hidden">Filter by campaign</span>
                <select
                  value={campaignId}
                  onChange={(event) => setCampaignId(event.target.value)}
                >
                  <option value="">All campaigns</option>
                  {campaigns.map((campaign) => (
                    <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
                  ))}
                </select>
              </label>
              <label>
                <span className="visually-hidden">Filter by lead source</span>
                <select
                  value={sourceType}
                  onChange={(event) => setSourceType(event.target.value)}
                >
                  <option value="">All lead sources</option>
                  {sourceOptions.map((value) => (
                    <option key={value} value={value}>{sourceLabel(value)}</option>
                  ))}
                </select>
              </label>
              <label>
                <span className="visually-hidden">Filter by stage</span>
                <select value={stage} onChange={(event) => setStage(event.target.value)}>
                  <option value="">All stages</option>
                  {PIPELINE_STAGES.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                </select>
              </label>
              <label>
                <span className="visually-hidden">Filter by suppression</span>
                <select value={suppression} onChange={(event) => setSuppression(event.target.value)}>
                  <option value="all">All contact states</option>
                  <option value="available">Available</option>
                  <option value="suppressed">Suppressed</option>
                </select>
              </label>
              <label>
                <span className="visually-hidden">Filter by review status</span>
                <select
                  value={reviewFilter}
                  onChange={(event) => setReviewFilter(event.target.value as "" | "review")}
                >
                  <option value="">All contact reviews</option>
                  <option value="review">Needs review</option>
                </select>
              </label>
            </div>

            {loading ? (
              <LoadingState label="Loading leads" />
            ) : filteredLeads.length === 0 ? (
              <EmptyState
                title={leads.length === 0 ? "No leads recorded" : "No leads match"}
                description={
                  leads.length === 0
                    ? "Manual entry is available as soon as a campaign exists."
                    : "Clear or broaden the active filters."
                }
              />
            ) : (
              <>
                <div className="table-wrap">
                  <table>
                  <thead>
                    <tr>
                      <th scope="col">Business</th>
                      <th scope="col">Score</th>
                      <th scope="col">Contact</th>
                      <th scope="col">Lead source</th>
                      <th scope="col">Stage</th>
                      <th scope="col">Location</th>
                      <th scope="col">Next action</th>
                      <th scope="col"><span className="visually-hidden">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {leadPages.items.map((lead) => {
                      const nextFollowUp = lead.follow_ups.find((item) => item.status === "open");
                      return (
                        <tr key={lead.id}>
                          <td data-label="Business">
                            <strong>{lead.business_name}</strong>
                            <small>{lead.segment}</small>
                            {lead.suppressed ? (
                              <span className="status-badge status-badge--warning">Do not contact</span>
                            ) : null}
                          </td>
                          <td data-label="Score">
                            {lead.current_score === null ? (
                              <span className="status-badge">Not scored</span>
                            ) : (
                              <span className={`score-chip${lead.current_score >= 70 ? " score-chip--strong" : ""}`}>
                                {lead.current_score}/100
                              </span>
                            )}
                          </td>
                          <td data-label="Contact">
                            {lead.phone_number ? <small>{lead.phone_number}</small> : null}
                            {lead.public_email ? <small>{lead.public_email}</small> : null}
                            {!lead.phone_number && !lead.public_email ? (
                              <small className="supporting-copy">Not on file</small>
                            ) : null}
                          </td>
                          <td data-label="Lead source">
                            <div className="lead-source-list">
                              {leadSourceTypes(lead).map((value) => (
                                <span className="status-badge" key={value}>{sourceLabel(value)}</span>
                              ))}
                            </div>
                          </td>
                          <td data-label="Stage"><span className="status-badge">{humanize(lead.pipeline_stage)}</span></td>
                          <td data-label="Location">{lead.location}</td>
                          <td data-label="Next action">{nextFollowUp?.due_date ?? "Not set"}</td>
                          <td data-label="Action">
                            <button className="tertiary-action" type="button" onClick={() => onManage(lead.id)}>
                              Manage <ArrowRight size={16} aria-hidden="true" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  </table>
                </div>
                <Pagination
                  page={leadPages.page}
                  pageCount={leadPages.pageCount}
                  pageSize={leadPages.pageSize}
                  totalItems={leadPages.totalItems}
                  itemLabel="leads"
                  onPageChange={leadPages.setPage}
                />
              </>
            )}
          </div>
          </TaskPanel>
        )}
      </section>
    </>
  );
}
