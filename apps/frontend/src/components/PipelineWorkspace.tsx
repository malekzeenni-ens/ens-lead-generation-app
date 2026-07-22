import {
  AtSign,
  CalendarCheck,
  Check,
  CircleDollarSign,
  Clock3,
  FileText,
  Gauge,
  Mail,
  MessageCircle,
  MessageSquareText,
  Save,
  ShieldAlert,
  ShieldOff,
  UserRoundCog,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  instagramDmUrl,
  instagramHandleFor,
  mailtoUrl,
  renderTemplate,
  whatsappUrl,
} from "../contact";
import {
  PIPELINE_STAGES,
  classificationLabel,
  formatCurrency,
  formatDate,
  formatDateTime,
  humanize,
  todayIso,
} from "../domain";
import { usePagination } from "../pagination";
import type { Campaign, Lead, Product, ProductFamily, ScoreRun, Template } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import {
  DangerConfirm,
  EmptyState,
  PageHeader,
  Pagination,
  SectionHeading,
  StatGrid,
  TaskPanel,
  TaskTabs,
} from "./DesignSystem";

interface PipelineWorkspaceProps {
  leads: Lead[];
  campaigns: Campaign[];
  scores: ScoreRun[];
  templates: Template[];
  productFamilies: ProductFamily[];
  selectedLeadId: string | null;
  onSelectLead: (leadId: string) => void;
}

function formValue(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function optionalNumber(value: string): number | null {
  return value ? Number(value) : null;
}

interface TimelineItem {
  id: string;
  type: string;
  title: string;
  detail: string;
  createdAt: string;
}

function timelineFor(lead: Lead): TimelineItem[] {
  return [
    ...lead.stage_events.map((event) => ({
      id: event.id,
      type: "Stage",
      title: humanize(event.new_stage),
      detail: event.reason ?? "Pipeline stage changed",
      createdAt: event.created_at,
    })),
    ...lead.notes.map((note) => ({
      id: note.id,
      type: "Note",
      title: "Note added",
      detail: note.content,
      createdAt: note.created_at,
    })),
    ...lead.follow_ups.map((followUp) => ({
      id: followUp.id,
      type: "Follow-up",
      title: `${humanize(followUp.follow_up_type)} · ${humanize(followUp.status)}`,
      detail: `Due ${formatDate(followUp.due_date)}${followUp.notes ? ` · ${followUp.notes}` : ""}`,
      createdAt: followUp.created_at,
    })),
    ...lead.communications.map((communication) => ({
      id: communication.id,
      type: "Communication",
      title: `${humanize(communication.channel)} · ${humanize(communication.sent_status)}`,
      detail: communication.subject ?? communication.content,
      createdAt: communication.created_at,
    })),
    ...lead.suppression_records.map((record) => ({
      id: record.id,
      type: "Suppression",
      title: `${humanize(record.suppression_type)} · ${record.active ? "Active" : "Lifted"}`,
      detail: record.reason,
      createdAt: record.effective_at,
    })),
  ].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export function PipelineWorkspace({
  leads,
  campaigns,
  scores,
  templates,
  productFamilies,
  selectedLeadId,
  onSelectLead,
}: PipelineWorkspaceProps) {
  const {
    busy,
    updateLead: onUpdate,
    changeLeadStage: onStage,
    addNote: onNote,
    addFollowUp: onFollowUp,
    completeFollowUp: onCompleteFollowUp,
    addCommunication: onCommunication,
    suppressLead: onSuppress,
    liftSuppression: onLiftSuppression,
    deleteLead: onDelete,
    calculateScore: onCalculateScore,
    overrideScore: onOverrideScore,
    sendContactMessage,
  } = useWorkspaceActions();
  const [activeTask, setActiveTask] = useState("overview");
  const [leadQuery, setLeadQuery] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const selectedLead = leads.find((lead) => lead.id === selectedLeadId) ?? leads[0] ?? null;
  const filteredLeads = useMemo(() => {
    const query = leadQuery.toLocaleLowerCase();
    return leads.filter((lead) =>
      [lead.business_name, lead.location, lead.phone_number ?? "", lead.public_email ?? ""].some(
        (value) => value.toLocaleLowerCase().includes(query),
      ),
    );
  }, [leadQuery, leads]);
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId) ?? null;
  const templateProducts = useMemo(() => {
    if (!selectedTemplate) return [];
    const byId = new Map<string, Product>();
    for (const familyId of selectedTemplate.product_family_ids) {
      const family = productFamilies.find((item) => item.id === familyId);
      for (const product of family?.products ?? []) {
        byId.set(product.id, product);
      }
    }
    return [...byId.values()];
  }, [productFamilies, selectedTemplate]);
  const renderedSubject = selectedLead && selectedTemplate
    ? renderTemplate(selectedTemplate.subject, selectedLead, templateProducts)
    : "";
  const renderedBody = selectedLead && selectedTemplate
    ? renderTemplate(selectedTemplate.body, selectedLead, templateProducts)
    : "";
  const instagramHandle = selectedLead ? instagramHandleFor(selectedLead) : null;
  const whatsappHref = selectedLead ? whatsappUrl(selectedLead.phone_number, renderedBody) : null;
  const emailHref = selectedLead
    ? mailtoUrl(selectedLead.public_email, renderedSubject, renderedBody)
    : null;
  const instagramHref = instagramDmUrl(instagramHandle);
  const timeline = selectedLead ? timelineFor(selectedLead) : [];
  const openFollowUps = selectedLead
    ? selectedLead.follow_ups.filter((item) => item.status === "open")
    : [];
  const leadPages = usePagination(filteredLeads, 8, leadQuery);
  const { pageSize: leadPageSize, setPage: setLeadPage } = leadPages;
  const followUpPages = usePagination(
    openFollowUps,
    5,
    selectedLead ? `${selectedLead.id}|${selectedLead.updated_at}` : "",
  );
  const timelinePages = usePagination(
    timeline,
    10,
    selectedLead ? `${selectedLead.id}|${selectedLead.updated_at}` : "",
  );
  const selectedScore = selectedLead
    ? scores.find((score) => score.lead_id === selectedLead.id) ?? null
    : null;

  useEffect(() => {
    if (!selectedLeadId) return;
    const selectedIndex = filteredLeads.findIndex((lead) => lead.id === selectedLeadId);
    if (selectedIndex >= 0) setLeadPage(Math.floor(selectedIndex / leadPageSize) + 1);
  }, [filteredLeads, leadPageSize, selectedLeadId, setLeadPage]);

  async function submitDetails(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const form = new FormData(event.currentTarget);
    await onUpdate(selectedLead.id, {
      business_name: formValue(form, "detail-name"),
      segment: formValue(form, "detail-segment"),
      location: formValue(form, "detail-location"),
      website: formValue(form, "detail-website") || null,
      instagram_url: formValue(form, "detail-instagram") || null,
      facebook_url: formValue(form, "detail-facebook") || null,
      phone_number: formValue(form, "detail-phone") || null,
      public_email: formValue(form, "detail-email") || null,
      contact_classification: formValue(form, "detail-classification"),
      retention_review_date: formValue(form, "detail-retention") || null,
    });
  }

  async function submitStage(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const form = new FormData(event.currentTarget);
    await onStage(
      selectedLead.id,
      formValue(form, "pipeline-stage"),
      formValue(form, "stage-reason") || undefined,
    );
  }

  async function submitOpportunity(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const form = new FormData(event.currentTarget);
    await onUpdate(selectedLead.id, {
      estimated_order_value: optionalNumber(formValue(form, "estimated-value")),
      quote_value: optionalNumber(formValue(form, "quote-value")),
      won_value: optionalNumber(formValue(form, "won-value")),
      potential_recurrence: formValue(form, "recurrence") || null,
      lost_reason: formValue(form, "lost-reason") || null,
      mock_up_status: formValue(form, "mock-status"),
      sample_status: formValue(form, "sample-status"),
      quote_status: formValue(form, "quote-status"),
    });
  }

  async function submitNote(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const formElement = event.currentTarget;
    const content = formValue(new FormData(formElement), "note-content");
    if (await onNote(selectedLead.id, content)) formElement.reset();
  }

  async function submitFollowUp(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const saved = await onFollowUp(selectedLead.id, {
      follow_up_type: formValue(form, "follow-up-type"),
      due_date: formValue(form, "follow-up-date"),
      notes: formValue(form, "follow-up-notes") || null,
    });
    if (saved) formElement.reset();
  }

  async function submitCommunication(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const saved = await onCommunication(selectedLead.id, {
      channel: formValue(form, "communication-channel"),
      subject: formValue(form, "communication-subject") || null,
      content: formValue(form, "communication-content"),
      sent_status: formValue(form, "communication-status"),
      user_confirmed: form.get("communication-confirmed") === "on",
      response_status: formValue(form, "response-status"),
    });
    if (saved) formElement.reset();
  }

  async function submitSuppression(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const form = new FormData(event.currentTarget);
    await onSuppress(selectedLead.id, {
      suppression_type: formValue(form, "suppression-type"),
      reason: formValue(form, "suppression-reason"),
      source: formValue(form, "suppression-source"),
      notes: formValue(form, "suppression-notes") || null,
    });
  }

  async function submitScoreOverride(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedLead) return;
    const form = new FormData(event.currentTarget);
    await onOverrideScore(
      selectedLead.id,
      Number(formValue(form, "score-override")),
      formValue(form, "score-override-reason"),
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Opportunity management"
        title="Pipeline"
        description="Track each prospect through an explicit, audited and entirely manual workflow."
      />

      <section className="workspace-section" aria-labelledby="pipeline-heading">
        <SectionHeading
          id="pipeline-heading"
          eyebrow="Lead operations"
          title="Pipeline workspace"
          description="Stage history, next actions and contact controls stay together."
          icon={UserRoundCog}
          count={leads.length}
        />

        {leads.length === 0 ? (
          <div className="records-panel">
            <EmptyState title="No leads to manage" description="Add a manual lead before opening the pipeline." />
          </div>
        ) : (
          <div className="pipeline-layout">
            <aside className="lead-selector" aria-label="Pipeline leads">
              <label>
                <span className="visually-hidden">Search pipeline leads</span>
                <input
                  value={leadQuery}
                  onChange={(event) => setLeadQuery(event.target.value)}
                  placeholder="Search pipeline"
                />
              </label>
              <div className="lead-selector__list">
                {leadPages.items.map((lead) => (
                  <button
                    type="button"
                    key={lead.id}
                    className={lead.id === selectedLead?.id ? "selected" : undefined}
                    onClick={() => onSelectLead(lead.id)}
                  >
                    <span>
                      <strong>{lead.business_name}</strong>
                      <small>{humanize(lead.pipeline_stage)}</small>
                    </span>
                    {lead.suppressed ? <ShieldOff size={16} aria-label="Suppressed" /> : null}
                  </button>
                ))}
              </div>
              <Pagination
                page={leadPages.page}
                pageCount={leadPages.pageCount}
                pageSize={leadPages.pageSize}
                totalItems={leadPages.totalItems}
                itemLabel="pipeline leads"
                onPageChange={leadPages.setPage}
                compact
              />
            </aside>

            {selectedLead ? (
              <div className="pipeline-detail" key={`${selectedLead.id}-${selectedLead.updated_at}`}>
                <div className="lead-detail-header">
                  <div>
                    <p className="eyebrow">Selected lead</p>
                    <h2>{selectedLead.business_name}</h2>
                    <p>{selectedLead.segment} · {selectedLead.location}</p>
                    <div className="lead-contact-routes">
                      {selectedLead.website ? (
                        <a href={selectedLead.website} target="_blank" rel="noreferrer">
                          {selectedLead.website}
                        </a>
                      ) : null}
                      {selectedLead.phone_number ? (
                        <a href={`tel:${selectedLead.phone_number}`}>{selectedLead.phone_number}</a>
                      ) : null}
                      {selectedLead.public_email ? (
                        <a href={`mailto:${selectedLead.public_email}`}>{selectedLead.public_email}</a>
                      ) : null}
                      {selectedLead.social_identities.map((identity) => (
                        <a
                          key={identity.id}
                          href={identity.profile_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {humanize(identity.platform)} @{identity.normalized_handle}
                        </a>
                      ))}
                    </div>
                  </div>
                  <div className="lead-detail-statuses">
                    <span className="status-badge">{humanize(selectedLead.pipeline_stage)}</span>
                    <span className={`status-badge${selectedLead.suppressed ? " status-badge--warning" : " status-badge--success"}`}>
                      {selectedLead.suppressed ? "Do not contact" : classificationLabel(selectedLead.contact_classification)}
                    </span>
                  </div>
                </div>

                {selectedLead.suppressed ? (
                  <div className="alert alert--warning" role="status">
                    <ShieldAlert size={20} aria-hidden="true" />
                    <div>
                      <strong>Suppression is active</strong>
                      <p>Stage movement, new follow-ups and sent communications are blocked.</p>
                    </div>
                    <button className="secondary-action" type="button" disabled={busy} onClick={() => void onLiftSuppression(selectedLead.id)}>
                      Lift suppression
                    </button>
                  </div>
                ) : null}

                <TaskTabs
                  id="lead-pipeline-tasks"
                  label={`Tasks for ${selectedLead.business_name}`}
                  activeId={activeTask}
                  onChange={setActiveTask}
                  items={[
                    { id: "overview", label: "Overview" },
                    { id: "contact", label: "Contact" },
                    { id: "score", label: "Score & products" },
                    { id: "opportunity", label: "Opportunity" },
                    { id: "activity", label: "Activity & follow-up", count: timeline.length },
                    { id: "privacy", label: "Privacy" },
                  ]}
                />

                {activeTask === "contact" ? (
                <TaskPanel id="lead-pipeline-tasks" tabId="contact">
                <section className="operation-card" aria-labelledby="contact-card-heading">
                  <div className="operation-card__heading">
                    <MessageSquareText size={18} aria-hidden="true" />
                    <div>
                      <h3 id="contact-card-heading">Send a message</h3>
                      <p>Pick a template, then open it in WhatsApp, email or Instagram to review and send yourself.</p>
                    </div>
                  </div>
                  <label>
                    Template
                    <select
                      value={selectedTemplateId}
                      onChange={(event) => setSelectedTemplateId(event.target.value)}
                    >
                      <option value="">Choose a template</option>
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>{template.topic}</option>
                      ))}
                    </select>
                  </label>
                  {templates.length === 0 ? (
                    <p className="form-hint">No templates yet — add one from the Templates workspace.</p>
                  ) : null}
                  {selectedTemplate ? (
                    <div className="contact-preview">
                      {renderedSubject ? <p><strong>Subject:</strong> {renderedSubject}</p> : null}
                      <p>{renderedBody}</p>
                    </div>
                  ) : null}
                  <div className="form-actions contact-actions">
                    <button
                      type="button"
                      className="secondary-action"
                      disabled={busy || !selectedTemplate || !whatsappHref}
                      onClick={() => {
                        if (!whatsappHref) return;
                        void sendContactMessage(
                          selectedLead.id,
                          "whatsapp",
                          whatsappHref,
                          "WhatsApp",
                          renderedBody,
                        );
                      }}
                    >
                      <MessageCircle size={16} aria-hidden="true" /> WhatsApp
                    </button>
                    <button
                      type="button"
                      className="secondary-action"
                      disabled={busy || !selectedTemplate || !emailHref}
                      onClick={() => {
                        if (!emailHref) return;
                        void sendContactMessage(
                          selectedLead.id,
                          "email",
                          emailHref,
                          "Email",
                          renderedBody,
                          renderedSubject,
                        );
                      }}
                    >
                      <Mail size={16} aria-hidden="true" /> Email
                    </button>
                    <button
                      type="button"
                      className="secondary-action"
                      disabled={busy || !selectedTemplate || !instagramHref}
                      onClick={() => {
                        if (!instagramHref) return;
                        void sendContactMessage(
                          selectedLead.id,
                          "instagram",
                          instagramHref,
                          "Instagram",
                          renderedBody,
                        );
                      }}
                    >
                      <AtSign size={16} aria-hidden="true" /> Instagram
                    </button>
                  </div>
                  {!selectedLead.phone_number ? (
                    <p className="form-hint">No phone number on file — WhatsApp is unavailable for this lead.</p>
                  ) : null}
                  {!selectedLead.public_email ? (
                    <p className="form-hint">No public email on file — Email is unavailable for this lead.</p>
                  ) : null}
                  {!instagramHandle ? (
                    <p className="form-hint">No Instagram profile on file — Instagram is unavailable for this lead.</p>
                  ) : null}
                  <p className="form-hint">
                    Instagram does not support pre-filling a message from a link; only the conversation opens, so
                    paste the text above once it does.
                  </p>
                </section>
                </TaskPanel>
                ) : null}

                {activeTask === "score" ? (
                <TaskPanel id="lead-pipeline-tasks" tabId="score">
                <section className="operation-card score-panel" aria-labelledby="score-card-heading">
                  <div className="operation-card__heading score-panel__heading">
                    <Gauge size={18} aria-hidden="true" />
                    <div>
                      <h3 id="score-card-heading">Qualification score</h3>
                      <p>Deterministic, versioned and fully explained. AI does not assign points.</p>
                    </div>
                    <span className={`score-chip${(selectedScore?.final_score ?? 0) >= 70 ? " score-chip--strong" : ""}`}>
                      {selectedScore ? `${selectedScore.final_score}/100` : "Not scored"}
                    </span>
                  </div>
                  <div className="score-controls">
                    <label>
                      Campaign model
                      <select id="score-campaign" defaultValue={selectedLead.campaign_ids[0] ?? ""}>
                        {campaigns
                          .filter((campaign) => selectedLead.campaign_ids.includes(campaign.id))
                          .map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}
                      </select>
                    </label>
                    <button
                      className="primary-action"
                      type="button"
                      disabled={busy || selectedLead.suppressed || selectedLead.campaign_ids.length === 0}
                      onClick={() => {
                        const select = document.querySelector<HTMLSelectElement>("#score-campaign");
                        if (select?.value) void onCalculateScore(selectedLead.id, select.value);
                      }}
                    >
                      <Gauge size={16} aria-hidden="true" /> Calculate score
                    </button>
                  </div>
                  {selectedScore ? (
                    <>
                      <div className="score-meta">
                        <span>{selectedScore.profile_name} · v{selectedScore.profile_version}</span>
                        <span>{selectedScore.rule_version}</span>
                        {selectedScore.manual_override ? (
                          <span className="status-badge status-badge--warning">
                            Manual override from {selectedScore.calculated_score}
                          </span>
                        ) : null}
                      </div>
                      <h4>Score breakdown</h4>
                      <div className="score-breakdown">
                        {selectedScore.breakdown.map((item) => (
                          <details key={item.category}>
                            <summary>
                              <span>{item.category}</span>
                              <strong>{item.points_awarded}/{item.points_available}</strong>
                            </summary>
                            <div>
                              <h4>Evidence used</h4>
                              {item.evidence_used.length ? (
                                <ul>{item.evidence_used.map((evidence) => <li key={evidence}>{evidence}</li>)}</ul>
                              ) : <p>None recorded.</p>}
                              <h4>Missing evidence</h4>
                              {item.missing_evidence.length ? (
                                <ul>{item.missing_evidence.map((missing) => <li key={missing}>{missing}</li>)}</ul>
                              ) : <p>No missing evidence for this category.</p>}
                            </div>
                          </details>
                        ))}
                      </div>
                      <div className="product-match-list">
                        <h4>Rule-based product matches</h4>
                        {selectedScore.product_matches.length ? selectedScore.product_matches.map((match) => (
                          <article key={match.product_id}>
                            <strong>{match.product_name}</strong>
                            <span>{match.match_score}% match</span>
                            <p>{match.reason}</p>
                          </article>
                        )) : <p>No active catalogue product matched this campaign and segment.</p>}
                      </div>
                      <h4>Manual override</h4>
                      <form className="score-override" onSubmit={(event) => void submitScoreOverride(event)}>
                        <label>Manual score<input name="score-override" type="number" min="0" max="100" required defaultValue={selectedScore.final_score} /></label>
                        <label>Override reason<input name="score-override-reason" minLength={3} maxLength={2000} required /></label>
                        <button className="secondary-action" type="submit" disabled={busy || selectedLead.suppressed}>
                          Save manual override
                        </button>
                      </form>
                    </>
                  ) : (
                    <p className="form-hint">Calculate the first score to see awarded points, missing evidence and product matches.</p>
                  )}
                </section>
                </TaskPanel>
                ) : null}

                {activeTask === "opportunity" ? (
                <TaskPanel id="lead-pipeline-tasks" tabId="opportunity">
                <div className="pipeline-card-grid">
                  <section className="operation-card" aria-labelledby="stage-card-heading">
                    <div className="operation-card__heading">
                      <Clock3 size={18} aria-hidden="true" />
                      <h3 id="stage-card-heading">Pipeline stage</h3>
                    </div>
                    <form className="form-grid form-grid--compact" onSubmit={(event) => void submitStage(event)}>
                      <label>Stage
                        <select name="pipeline-stage" defaultValue={selectedLead.pipeline_stage} disabled={selectedLead.suppressed}>
                          {PIPELINE_STAGES.map((stage) => <option key={stage} value={stage}>{humanize(stage)}</option>)}
                        </select>
                      </label>
                      <label>Reason <span className="optional-label">Optional</span>
                        <input name="stage-reason" maxLength={2000} />
                      </label>
                      <button className="primary-action" type="submit" disabled={busy || selectedLead.suppressed}>
                        <Save size={16} aria-hidden="true" /> Change stage
                      </button>
                    </form>
                  </section>

                  <section className="operation-card" aria-labelledby="value-card-heading">
                    <div className="operation-card__heading">
                      <CircleDollarSign size={18} aria-hidden="true" />
                      <h3 id="value-card-heading">Opportunity value</h3>
                    </div>
                    <StatGrid
                      className="value-summary"
                      items={[
                        { label: "Estimate", value: formatCurrency(selectedLead.estimated_order_value) },
                        { label: "Quote", value: formatCurrency(selectedLead.quote_value) },
                        { label: "Won", value: formatCurrency(selectedLead.won_value) },
                      ]}
                    />
                    <form className="form-grid form-grid--compact" onSubmit={(event) => void submitOpportunity(event)}>
                      <div className="field-trio">
                        <label>Estimate (£)<input name="estimated-value" type="number" min="0" step="0.01" defaultValue={selectedLead.estimated_order_value ?? ""} /></label>
                        <label>Quote (£)<input name="quote-value" type="number" min="0" step="0.01" defaultValue={selectedLead.quote_value ?? ""} /></label>
                        <label>Won (£)<input name="won-value" type="number" min="0" step="0.01" defaultValue={selectedLead.won_value ?? ""} /></label>
                      </div>
                      <div className="field-pair">
                        <label>Recurrence<input name="recurrence" maxLength={100} defaultValue={selectedLead.potential_recurrence ?? ""} /></label>
                        <label>Lost reason
                          <select name="lost-reason" defaultValue={selectedLead.lost_reason ?? ""}>
                            <option value="">Not set</option>
                            {[
                              "no_response", "not_interested", "price", "no_current_need",
                              "already_has_supplier", "outside_scope", "other",
                            ].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                          </select>
                        </label>
                      </div>
                      <div className="field-trio">
                        <label>Mock-up
                          <select name="mock-status" defaultValue={selectedLead.mock_up_status}>
                            {["not_offered", "offered", "requested", "in_progress", "sent", "approved", "rejected"].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                          </select>
                        </label>
                        <label>Sample
                          <select name="sample-status" defaultValue={selectedLead.sample_status}>
                            {["not_applicable", "under_consideration", "approved", "sent", "declined"].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                          </select>
                        </label>
                        <label>Quote
                          <select name="quote-status" defaultValue={selectedLead.quote_status}>
                            {["not_requested", "requested", "preparing", "sent", "accepted", "declined"].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                          </select>
                        </label>
                      </div>
                      <button className="secondary-action" type="submit" disabled={busy}><Save size={16} /> Save opportunity</button>
                    </form>
                  </section>
                </div>
                </TaskPanel>
                ) : null}

                {activeTask === "overview" ? (
                <TaskPanel id="lead-pipeline-tasks" tabId="overview">
                <details className="operation-disclosure" open>
                  <summary><FileText size={17} aria-hidden="true" /> Lead details and retention</summary>
                  <form className="form-grid" onSubmit={(event) => void submitDetails(event)}>
                    <div className="field-pair">
                      <label>Business name<input name="detail-name" required defaultValue={selectedLead.business_name} /></label>
                      <label>Location<input name="detail-location" required defaultValue={selectedLead.location} /></label>
                    </div>
                    <label>Segment<input name="detail-segment" required defaultValue={selectedLead.segment} /></label>
                    <div className="field-pair">
                      <label>Website<input name="detail-website" type="url" defaultValue={selectedLead.website ?? ""} /></label>
                      <label>Public phone<input name="detail-phone" type="tel" defaultValue={selectedLead.phone_number ?? ""} /></label>
                    </div>
                    <div className="field-pair">
                      <label>Public email<input name="detail-email" type="email" defaultValue={selectedLead.public_email ?? ""} /></label>
                      <label>Preferred social profile<input type="url" value={selectedLead.social_profile ?? ""} readOnly /></label>
                    </div>
                    <div className="field-pair">
                      <label>Instagram profile<input name="detail-instagram" type="url" defaultValue={selectedLead.social_identities.find((item) => item.platform === "instagram")?.profile_url ?? ""} /></label>
                      <label>Facebook page<input name="detail-facebook" type="url" defaultValue={selectedLead.social_identities.find((item) => item.platform === "facebook")?.profile_url ?? ""} /></label>
                    </div>
                    <div className="field-pair">
                      <label>Contact classification
                        <select name="detail-classification" defaultValue={selectedLead.contact_classification}>
                          <option value="unknown">Unknown — review required</option>
                          <option value="corporate_subscriber">Corporate subscriber</option>
                          <option value="sole_trader_or_individual">Sole trader / individual</option>
                          <option value="partnership_individual_treatment">Partnership review</option>
                        </select>
                      </label>
                      <label>Retention review<input name="detail-retention" type="date" defaultValue={selectedLead.retention_review_date ?? ""} /></label>
                    </div>
                    <button className="secondary-action" type="submit" disabled={busy}><Save size={16} /> Save lead details</button>
                  </form>
                </details>
                </TaskPanel>
                ) : null}

                {activeTask === "activity" ? (
                <TaskPanel id="lead-pipeline-tasks" tabId="activity">
                <div className="section-layout">
                  <div className="pipeline-activity-forms">
                    <section className="operation-card">
                      <div className="operation-card__heading"><FileText size={18} /><h3>Notes</h3></div>
                      <form className="form-grid form-grid--compact" onSubmit={(event) => void submitNote(event)}>
                        <label>New note<textarea name="note-content" rows={3} required maxLength={10000} /></label>
                        <button className="secondary-action" type="submit" disabled={busy}>Add note</button>
                      </form>
                    </section>

                    <section className="operation-card">
                      <div className="operation-card__heading"><CalendarCheck size={18} /><h3>Next action</h3></div>
                      <form className="form-grid form-grid--compact" onSubmit={(event) => void submitFollowUp(event)}>
                        <div className="field-pair">
                          <label>Type
                            <select name="follow-up-type" defaultValue="general">
                              {["email", "instagram", "mock_up", "sample", "quote", "general"].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                            </select>
                          </label>
                          <label>Due date<input name="follow-up-date" type="date" min={todayIso()} defaultValue={todayIso()} required /></label>
                        </div>
                        <label>Notes<input name="follow-up-notes" maxLength={2000} /></label>
                        <button className="secondary-action" type="submit" disabled={busy || selectedLead.suppressed}>Create follow-up</button>
                      </form>
                      <div className="compact-list">
                        {followUpPages.items.map((followUp) => (
                          <div key={followUp.id}>
                            <span><strong>{humanize(followUp.follow_up_type)}</strong><small>{formatDate(followUp.due_date)}</small></span>
                            <button className="tertiary-action" type="button" disabled={busy} onClick={() => void onCompleteFollowUp(selectedLead.id, followUp.id)}>
                              <Check size={15} /> Complete
                            </button>
                          </div>
                        ))}
                      </div>
                      <Pagination
                        page={followUpPages.page}
                        pageCount={followUpPages.pageCount}
                        pageSize={followUpPages.pageSize}
                        totalItems={followUpPages.totalItems}
                        itemLabel="open follow-ups"
                        onPageChange={followUpPages.setPage}
                        compact
                      />
                    </section>

                    <section className="operation-card">
                      <div className="operation-card__heading"><MessageSquareText size={18} /><h3>Manual communication</h3></div>
                      <form className="form-grid form-grid--compact" onSubmit={(event) => void submitCommunication(event)}>
                        <div className="field-pair">
                          <label>Channel
                            <select name="communication-channel" defaultValue="email">
                              {['email', 'instagram', 'phone', 'whatsapp', 'other'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
                            </select>
                          </label>
                          <label>Status
                            <select name="communication-status" defaultValue="recorded">
                              <option value="recorded">Recorded only</option>
                              <option value="sent">Sent manually</option>
                              <option value="received">Received</option>
                              <option value="draft">Draft</option>
                            </select>
                          </label>
                        </div>
                        <label>Subject<input name="communication-subject" maxLength={300} /></label>
                        <label>Content<textarea name="communication-content" rows={3} required maxLength={50000} /></label>
                        <label>Response
                          <select name="response-status" defaultValue="none">
                            <option value="none">None</option>
                            <option value="replied">Replied</option>
                            <option value="no_response">No response</option>
                          </select>
                        </label>
                        <label className="checkbox-field"><input name="communication-confirmed" type="checkbox" /> I confirm any “sent” item was sent manually</label>
                        <button className="secondary-action" type="submit" disabled={busy}>Record communication</button>
                      </form>
                    </section>
                  </div>

                  <section className="timeline-panel" aria-labelledby="timeline-heading">
                    <div className="records-heading">
                      <div><h3 id="timeline-heading">Activity timeline</h3><p>Chronological local history</p></div>
                      <span>{timeline.length} events</span>
                    </div>
                    <ol className="timeline-list">
                      {timelinePages.items.map((item) => (
                        <li key={`${item.type}-${item.id}`}>
                          <span className="timeline-marker" aria-hidden="true" />
                          <div>
                            <span>{item.type} · {formatDateTime(item.createdAt)}</span>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                          </div>
                        </li>
                      ))}
                    </ol>
                    <Pagination
                      page={timelinePages.page}
                      pageCount={timelinePages.pageCount}
                      pageSize={timelinePages.pageSize}
                      totalItems={timelinePages.totalItems}
                      itemLabel="activity events"
                      onPageChange={timelinePages.setPage}
                    />
                  </section>
                </div>
                </TaskPanel>
                ) : null}

                {activeTask === "privacy" ? (
                <TaskPanel id="lead-pipeline-tasks" tabId="privacy">
                <div className="pipeline-privacy-layout">
                  <section className="operation-card operation-card--danger">
                    <div className="operation-card__heading"><ShieldAlert size={18} /><h3>Suppression and privacy</h3></div>
                    {!selectedLead.suppressed ? (
                      <form className="form-grid form-grid--compact" onSubmit={(event) => void submitSuppression(event)}>
                        <label>Suppression type
                          <select name="suppression-type" defaultValue="do_not_contact">
                            <option value="do_not_contact">Do not contact</option>
                            <option value="unsubscribe">Unsubscribe</option>
                            <option value="objection">Objection</option>
                          </select>
                        </label>
                        <label>Reason<textarea name="suppression-reason" required rows={2} maxLength={2000} /></label>
                        <label>Source<input name="suppression-source" required defaultValue="Local user" maxLength={100} /></label>
                        <label>Notes<input name="suppression-notes" maxLength={2000} /></label>
                        <button className="danger-action" type="submit" disabled={busy}><ShieldOff size={16} /> Apply suppression</button>
                      </form>
                    ) : (
                      <p className="supporting-copy">Active suppression evidence will survive lead deletion in minimised form.</p>
                    )}
                    <div>
                      <p><strong>Delete personal lead data</strong></p>
                      <p>Type DELETE to remove the lead, sources, history, notes and follow-ups.</p>
                      <DangerConfirm
                        key={selectedLead.id}
                        intensity="type-to-confirm"
                        label="Delete lead data"
                        confirmText="DELETE"
                        disabled={busy}
                        onConfirm={() => void onDelete(selectedLead.id)}
                      />
                    </div>
                  </section>
                </div>
                </TaskPanel>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </section>
    </>
  );
}
