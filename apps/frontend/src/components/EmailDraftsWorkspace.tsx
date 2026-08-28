import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  CirclePause,
  ExternalLink,
  FileEdit,
  MailCheck,
  RotateCcw,
  Save,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import { emailAddressFor } from "../contact";
import { classificationLabel, formatDateTime, humanize, todayIso } from "../domain";
import type {
  Campaign,
  Lead,
  OutreachBatch,
  OutreachDraft,
  OutreachLeadOption,
  Template,
} from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import {
  EmptyState,
  GuidanceNote,
  HelpTip,
  LoadingState,
  PageHeader,
  SectionHeading,
  TaskPanel,
  TaskTabs,
} from "./DesignSystem";

interface EmailDraftsWorkspaceProps {
  campaigns: Campaign[];
  leads: Lead[];
  templates: Template[];
  leadOptions: OutreachLeadOption[];
  batches: OutreachBatch[];
}

interface DraftEditorProps {
  draft: OutreachDraft;
}

function reviewLabel(draft: OutreachDraft): string {
  if (draft.sync_status === "user_confirmed_sent") return "Sent (confirmed)";
  if (draft.review_status === "pending_review") return "Needs review";
  return humanize(draft.review_status);
}

function reviewTone(draft: OutreachDraft): string {
  if (draft.review_status === "approved") return " status-badge--success";
  if (draft.review_status === "pending_review") return " status-badge--warning";
  return " status-badge--error";
}

function reviewDescription(draft: OutreachDraft): string {
  if (draft.sync_status === "user_confirmed_sent") {
    return "You confirmed the approved version was sent, so this draft is closed and recorded on the lead timeline.";
  }
  if (draft.sync_status === "opened_in_zoho") {
    return "The approved version was opened in Zoho, but sending has not been confirmed.";
  }
  if (draft.review_status === "approved") {
    return "This exact version is approved and ready to open in Zoho. It has not been sent.";
  }
  if (draft.review_status === "pending_review") {
    return "Review and personalise this version before approving or rejecting it.";
  }
  return "This draft is closed locally and will not be sent. It can be reopened for editing.";
}

function DraftEditor({ draft }: DraftEditorProps) {
  const {
    busy,
    manageLead,
    editOutreachDraft,
    approveOutreachDraft,
    rejectOutreachDraft,
    reopenOutreachDraft,
    openOutreachDraftInZoho,
    confirmOutreachDraftSent,
  } = useWorkspaceActions();
  const [subject, setSubject] = useState(draft.current_revision.subject);
  const [body, setBody] = useState(draft.current_revision.body);
  const [showReject, setShowReject] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const dirty =
    subject !== draft.current_revision.subject || body !== draft.current_revision.body;
  const rejected = draft.review_status === "rejected";
  const openedInZoho = draft.sync_status === "opened_in_zoho";
  const sentConfirmed = draft.sync_status === "user_confirmed_sent";

  async function save(): Promise<boolean> {
    if (!dirty) return true;
    return editOutreachDraft(draft.id, { subject: subject.trim(), body: body.trim() });
  }

  async function saveAndApprove(): Promise<void> {
    if (!(await save())) return;
    await approveOutreachDraft(draft.id);
  }

  async function submitReject(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const completed = await rejectOutreachDraft(draft.id, rejectionReason);
    if (completed) setShowReject(false);
  }

  return (
    <article className="draft-editor" aria-labelledby="draft-editor-heading">
      <div className="draft-editor__header">
        <div>
          <p className="eyebrow">Personalise and decide</p>
          <h2 id="draft-editor-heading">{draft.business_name}</h2>
          <p>
            To {draft.recipient_email} · {draft.location}
          </p>
        </div>
        <span className="status-with-help">
          <span className={`status-badge${reviewTone(draft)}`}>{reviewLabel(draft)}</span>
          <HelpTip label={`About ${reviewLabel(draft)} status`}>
            {reviewDescription(draft)}
          </HelpTip>
        </span>
      </div>

      {draft.blocked_reason ? (
        <div className="form-notice form-notice--warning">
          <AlertTriangle size={17} aria-hidden="true" />
          <span>{draft.blocked_reason}</span>
        </div>
      ) : null}
      {draft.review_status === "approved" && dirty ? (
        <div className="form-notice form-notice--warning">
          <AlertTriangle size={17} aria-hidden="true" />
          <span>Changing approved content requires approval again.</span>
        </div>
      ) : null}
      {rejected ? (
        <div className="form-notice">
          <XCircle size={17} aria-hidden="true" />
          <span>
            This draft stays local and will not be sent anywhere.
            {draft.rejection_reason ? ` Reason: ${draft.rejection_reason}` : ""}
          </span>
        </div>
      ) : null}
      {openedInZoho ? (
        <div className="form-notice form-notice--warning">
          <AlertTriangle size={17} aria-hidden="true" />
          <span>
            Zoho was opened for this approved version, but sending is not confirmed. After you
            send it in Zoho, return here and choose Mark as sent.
          </span>
        </div>
      ) : null}
      {sentConfirmed ? (
        <div className="form-notice">
          <CheckCircle2 size={17} aria-hidden="true" />
          <span>
            You confirmed this email was sent. It is now recorded in the lead activity timeline.
          </span>
        </div>
      ) : null}

      <div className="draft-context-grid">
        <div>
          <span>Pipeline</span>
          <strong>{humanize(draft.pipeline_stage)}</strong>
        </div>
        <div>
          <span>Contact type</span>
          <strong>{classificationLabel(draft.contact_classification)}</strong>
        </div>
        <div>
          <span>Score</span>
          <strong>{draft.current_score ?? "Not scored"}</strong>
        </div>
        <div>
          <span>Version</span>
          <strong>v{draft.current_version}</strong>
        </div>
      </div>

      <label>
        Subject
        <input
          value={subject}
          maxLength={300}
          disabled={busy || rejected || sentConfirmed}
          onChange={(event) => setSubject(event.target.value)}
        />
      </label>
      <label>
        Email body
        <textarea
          className="draft-body"
          value={body}
          maxLength={50_000}
          disabled={busy || rejected || sentConfirmed}
          onChange={(event) => setBody(event.target.value)}
        />
      </label>

      <div className="draft-editor__actions">
        {rejected ? (
          <button
            className="primary-action"
            type="button"
            disabled={busy}
            onClick={() => void reopenOutreachDraft(draft.id)}
          >
            <RotateCcw size={17} aria-hidden="true" />
            Reopen draft
          </button>
        ) : sentConfirmed ? null : (
          <>
            <button
              className="secondary-action"
              type="button"
              disabled={busy || !dirty || !subject.trim() || !body.trim()}
              onClick={() => void save()}
            >
              <Save size={17} aria-hidden="true" />
              Save changes
            </button>
            <button
              className="primary-action"
              type="button"
              title="Approve this exact version; this does not send the email"
              disabled={
                busy ||
                !subject.trim() ||
                !body.trim() ||
                (draft.review_status === "approved" && !dirty)
              }
              onClick={() => void saveAndApprove()}
            >
              <Check size={17} aria-hidden="true" />
              {dirty ? "Save and approve" : "Approve draft"}
            </button>
            <button
              className="danger-action"
              type="button"
              disabled={busy}
              title="Close this draft locally without changing the lead; it can be reopened"
              onClick={() => setShowReject((current) => !current)}
            >
              <XCircle size={17} aria-hidden="true" />
              Reject
            </button>
            {draft.review_status === "approved" && !dirty ? (
              <button
                className={openedInZoho ? "secondary-action" : "primary-action"}
                type="button"
                disabled={busy}
                title="Log this handoff, copy the body and open the approved version in your default email app"
                onClick={() => void openOutreachDraftInZoho(draft.id)}
              >
                <ExternalLink size={17} aria-hidden="true" />
                {openedInZoho ? "Open in Zoho again" : "Open in Zoho to send"}
              </button>
            ) : null}
            {openedInZoho && draft.review_status === "approved" && !dirty ? (
              <button
                className="primary-action"
                type="button"
                disabled={busy}
                title="Use only after the approved email has actually been sent in Zoho"
                onClick={() => {
                  if (
                    window.confirm(
                      "Confirm only after you have sent this email in Zoho. Mark it as sent?",
                    )
                  ) {
                    void confirmOutreachDraftSent(draft.id);
                  }
                }}
              >
                <CheckCircle2 size={17} aria-hidden="true" />
                Mark as sent
              </button>
            ) : null}
          </>
        )}
        <button
          className="tertiary-action"
          type="button"
          onClick={() => manageLead(draft.lead_id)}
        >
          View lead
        </button>
      </div>

      {draft.review_status === "approved" && !sentConfirmed ? (
        <p className="draft-handoff-help">
          Zoho opens through your computer&apos;s default email app. Set Zoho Mail as the default
          once if another composer opens. The approved body is also copied to your clipboard.
        </p>
      ) : null}

      {showReject && !rejected ? (
        <form className="draft-reject-form" onSubmit={(event) => void submitReject(event)}>
          <label>
            Rejection reason (optional)
            <input
              value={rejectionReason}
              maxLength={2_000}
              placeholder="For example: timing is not right"
              onChange={(event) => setRejectionReason(event.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="danger-action" type="submit" disabled={busy}>
              Confirm rejection
            </button>
            <button
              className="secondary-action"
              type="button"
              onClick={() => setShowReject(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      <aside className="draft-notes" aria-label="Lead context">
        <strong>Recent lead notes</strong>
        {draft.latest_notes.length > 0 ? (
          <ul>
            {draft.latest_notes.map((note, index) => (
              <li key={`${draft.id}-note-${index}`}>{note}</li>
            ))}
          </ul>
        ) : (
          <p>No notes have been added to this lead.</p>
        )}
      </aside>
    </article>
  );
}

interface HoldEditorProps {
  lead: OutreachLeadOption;
  onDone: () => void;
}

function HoldEditor({ lead, onDone }: HoldEditorProps) {
  const { busy, updateLead } = useWorkspaceActions();
  const [reason, setReason] = useState(lead.outreach_hold_reason ?? "");
  const [until, setUntil] = useState(lead.outreach_hold_until ?? "");

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (await updateLead(lead.id, { outreach_hold_reason: reason, outreach_hold_until: until })) {
      onDone();
    }
  }

  async function clear(): Promise<void> {
    if (
      await updateLead(lead.id, {
        outreach_hold_reason: null,
        outreach_hold_until: null,
      })
    ) {
      onDone();
    }
  }

  return (
    <form className="lead-hold-editor" onSubmit={(event) => void submit(event)}>
      <label>
        Hold reason
        <input
          required
          value={reason}
          maxLength={2_000}
          placeholder="For example: waiting for new product launch"
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <label>
        Hold until
        <input
          required
          type="date"
          min={todayIso()}
          value={until}
          onChange={(event) => setUntil(event.target.value)}
        />
      </label>
      <div className="form-actions">
        <button className="primary-action" type="submit" disabled={busy}>
          Save hold
        </button>
        {lead.outreach_hold_reason ? (
          <button
            className="secondary-action"
            type="button"
            disabled={busy}
            onClick={() => void clear()}
          >
            Clear hold
          </button>
        ) : null}
        <button className="tertiary-action" type="button" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function EmailDraftsWorkspace({
  campaigns,
  leads,
  templates,
  leadOptions,
  batches,
}: EmailDraftsWorkspaceProps) {
  const { busy, loading, createOutreachBatch, approveOutreachDrafts } =
    useWorkspaceActions();
  const [activeTask, setActiveTask] = useState<"prepare" | "review">(
    batches.some((batch) => batch.pending_count > 0) ? "review" : "prepare",
  );
  const [campaignId, setCampaignId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [selectedDraftId, setSelectedDraftId] = useState("");
  const [selectedApprovalIds, setSelectedApprovalIds] = useState<string[]>([]);
  const [holdLeadId, setHoldLeadId] = useState<string | null>(null);
  const selectedTemplateId = templateId || templates[0]?.id || "";
  const recipientEmailByLeadId = useMemo(
    () => new Map(leads.map((lead) => [lead.id, emailAddressFor(lead)])),
    [leads],
  );

  const visibleLeadOptions = useMemo(() => {
    const campaignLeadIds = campaignId
      ? new Set(
          leads
            .filter((lead) => lead.campaign_ids.includes(campaignId))
            .map((lead) => lead.id),
        )
      : null;
    return leadOptions
      .filter((lead) => !campaignLeadIds || campaignLeadIds.has(lead.id))
      .sort(
        (left, right) =>
          Number(right.ready) - Number(left.ready) ||
          left.business_name.localeCompare(right.business_name),
      );
  }, [campaignId, leadOptions, leads]);
  const readyLeads = visibleLeadOptions.filter((lead) => lead.ready);
  const selectedBatch =
    batches.find((batch) => batch.id === selectedBatchId) ?? batches[0] ?? null;
  const selectedDraft =
    selectedBatch?.drafts.find((draft) => draft.id === selectedDraftId) ??
    selectedBatch?.drafts[0] ??
    null;
  const approvalIds = selectedApprovalIds.filter((draftId) =>
    selectedBatch?.drafts.some(
      (draft) => draft.id === draftId && draft.review_status === "pending_review",
    ),
  );
  const pendingTotal = batches.reduce((total, batch) => total + batch.pending_count, 0);

  function toggleLead(leadId: string): void {
    setSelectedLeadIds((current) =>
      current.includes(leadId)
        ? current.filter((id) => id !== leadId)
        : current.length < 50
          ? [...current, leadId]
          : current,
    );
  }

  async function createBatch(): Promise<void> {
    if (!selectedTemplateId || selectedLeadIds.length === 0) return;
    const batchId = await createOutreachBatch({
      lead_ids: selectedLeadIds,
      template_id: selectedTemplateId,
      campaign_id: campaignId || null,
    });
    if (!batchId) return;
    setSelectedLeadIds([]);
    setSelectedBatchId(batchId);
    setSelectedDraftId("");
    setActiveTask("review");
  }

  function toggleApproval(draftId: string): void {
    setSelectedApprovalIds((current) =>
      current.includes(draftId)
        ? current.filter((id) => id !== draftId)
        : [...current, draftId],
    );
  }

  async function approveSelected(): Promise<void> {
    if (approvalIds.length === 0) return;
    const confirmed = window.confirm(
      `Approve ${approvalIds.length} selected draft${approvalIds.length === 1 ? "" : "s"}?\n\nEach exact draft version will become ready to open in Zoho. Nothing will be sent automatically.`,
    );
    if (!confirmed) return;
    if (await approveOutreachDrafts(approvalIds)) setSelectedApprovalIds([]);
  }

  return (
    <>
      <PageHeader
        eyebrow="Lead operations"
        title="Email drafts"
        description="Prepare and approve emails here, then open an approved version in Zoho. You stay in control of the final send."
        action={
          <div className="phase-badge">
            <ShieldCheck size={17} aria-hidden="true" />
            Assisted Zoho handoff
          </div>
        }
      />

      <GuidanceNote title="Approval is not sending">
        Edit each draft for your personal touch. Approval only makes that exact version ready for
        Zoho; opening Zoho is logged, and the email is recorded as sent only after you explicitly
        confirm it here.
      </GuidanceNote>

      <TaskTabs
        id="email-draft-tasks"
        label="Email draft tasks"
        items={[
          { id: "prepare", label: "Prepare drafts", count: readyLeads.length },
          { id: "review", label: "Review drafts", count: pendingTotal },
        ]}
        activeId={activeTask}
        onChange={(task) => setActiveTask(task as "prepare" | "review")}
      />

      {activeTask === "prepare" ? (
        <TaskPanel id="email-draft-tasks" tabId="prepare">
          <section className="workspace-section" aria-labelledby="prepare-drafts-heading">
            <SectionHeading
              id="prepare-drafts-heading"
              eyebrow="Step 1"
              title="Choose leads and a template"
              description="Only contact-ready leads can be selected. Warnings and recent notes remain visible for your decision."
              icon={FileEdit}
              count={selectedLeadIds.length}
            />

            <div className="draft-setup-bar">
              <label>
                Campaign
                <select value={campaignId} onChange={(event) => setCampaignId(event.target.value)}>
                  <option value="">All campaigns</option>
                  {campaigns.map((campaign) => (
                    <option key={campaign.id} value={campaign.id}>
                      {campaign.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Email template
                <select
                  value={selectedTemplateId}
                  disabled={templates.length === 0}
                  onChange={(event) => setTemplateId(event.target.value)}
                >
                  {templates.length === 0 ? <option value="">No templates available</option> : null}
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.topic}
                    </option>
                  ))}
                </select>
              </label>
              <div className="draft-setup-actions">
                <button
                  className="secondary-action"
                  type="button"
                  disabled={readyLeads.length === 0}
                  onClick={() => setSelectedLeadIds(readyLeads.slice(0, 50).map((lead) => lead.id))}
                >
                  Select eligible
                </button>
                <button
                  className="primary-action"
                  type="button"
                  disabled={busy || !selectedTemplateId || selectedLeadIds.length === 0}
                  onClick={() => void createBatch()}
                >
                  <MailCheck size={17} aria-hidden="true" />
                  Create {selectedLeadIds.length || ""} draft{selectedLeadIds.length === 1 ? "" : "s"}
                </button>
              </div>
            </div>

            {loading ? (
              <LoadingState label="Checking lead eligibility" />
            ) : templates.length === 0 ? (
              <EmptyState
                title="Add an email template first"
                description="Create a reusable subject and body in the Templates workspace, then return here."
              />
            ) : visibleLeadOptions.length === 0 ? (
              <EmptyState
                title="No leads in this view"
                description="Choose another campaign or add leads before preparing drafts."
              />
            ) : (
              <div className="draft-lead-list">
                {visibleLeadOptions.map((lead) => {
                  const checked = selectedLeadIds.includes(lead.id);
                  return (
                    <article
                      key={lead.id}
                      className={`draft-lead-row${checked ? " draft-lead-row--selected" : ""}`}
                    >
                      <label className="draft-lead-choice">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={!lead.ready || (!checked && selectedLeadIds.length >= 50)}
                          onChange={() => toggleLead(lead.id)}
                        />
                        <span>
                          <strong>{lead.business_name}</strong>
                          <small>
                            {recipientEmailByLeadId.get(lead.id) ?? "No email"} · {lead.location}
                          </small>
                        </span>
                      </label>
                      <div className="draft-lead-status">
                        <span
                          className={`status-badge${
                            lead.ready ? " status-badge--success" : " status-badge--warning"
                          }`}
                        >
                          {lead.ready ? "Eligible" : "Needs attention"}
                        </span>
                        <button
                          className="tertiary-action"
                          type="button"
                          onClick={() => setHoldLeadId(holdLeadId === lead.id ? null : lead.id)}
                        >
                          <CirclePause size={15} aria-hidden="true" />
                          {lead.outreach_hold_reason ? "Manage hold" : "Add hold"}
                        </button>
                      </div>
                      <details className="draft-lead-details">
                        <summary>Checks and notes</summary>
                        <div>
                          {lead.blockers.map((item) => (
                            <p className="check-message check-message--blocked" key={item}>
                              <XCircle size={15} aria-hidden="true" /> {item}
                            </p>
                          ))}
                          {lead.warnings.map((item) => (
                            <p className="check-message check-message--warning" key={item}>
                              <AlertTriangle size={15} aria-hidden="true" /> {item}
                            </p>
                          ))}
                          {lead.ready && lead.warnings.length === 0 ? (
                            <p className="check-message check-message--ready">
                              <CheckCircle2 size={15} aria-hidden="true" /> Account and contact
                              checks passed.
                            </p>
                          ) : null}
                          {lead.latest_notes.length > 0 ? (
                            <ul>
                              {lead.latest_notes.map((note, index) => (
                                <li key={`${lead.id}-note-${index}`}>{note}</li>
                              ))}
                            </ul>
                          ) : (
                            <p>No lead notes recorded.</p>
                          )}
                        </div>
                      </details>
                      {holdLeadId === lead.id ? (
                        <HoldEditor lead={lead} onDone={() => setHoldLeadId(null)} />
                      ) : null}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </TaskPanel>
      ) : (
        <TaskPanel id="email-draft-tasks" tabId="review">
          <section className="workspace-section" aria-labelledby="review-drafts-heading">
            <SectionHeading
              id="review-drafts-heading"
              eyebrow="Step 2"
              title="Review and decide"
              description="Edit for your personal touch. Saving an edit removes any previous approval until you approve the new version."
              icon={MailCheck}
              count={pendingTotal}
            />

            {loading ? (
              <LoadingState label="Loading draft batches" />
            ) : !selectedBatch ? (
              <EmptyState
                title="No drafts to review"
                description="Choose leads in Prepare drafts to create your first local review batch."
                action={
                  <button className="primary-action" type="button" onClick={() => setActiveTask("prepare")}>
                    Prepare drafts
                  </button>
                }
              />
            ) : (
              <>
                <div className="draft-review-toolbar">
                  <label>
                    Draft batch
                    <select
                      value={selectedBatch.id}
                      onChange={(event) => {
                        setSelectedBatchId(event.target.value);
                        setSelectedDraftId("");
                        setSelectedApprovalIds([]);
                      }}
                    >
                      {batches.map((batch) => (
                        <option key={batch.id} value={batch.id}>
                          {batch.template_topic ?? "Deleted template"} · {formatDateTime(batch.created_at)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="batch-counts" aria-label="Batch progress">
                    <span>{selectedBatch.pending_count} review</span>
                    <span>{selectedBatch.approved_count} approved</span>
                    <span>{selectedBatch.rejected_count} rejected</span>
                    <span>{selectedBatch.sent_count} sent</span>
                  </div>
                  <button
                    className="primary-action"
                    type="button"
                    disabled={busy || approvalIds.length === 0}
                    title="Approve the selected exact versions after confirmation; no email is sent"
                    onClick={() => void approveSelected()}
                  >
                    <Check size={17} aria-hidden="true" />
                    Approve selected ({approvalIds.length})
                  </button>
                </div>

                <div className="draft-review-layout">
                  <div className="draft-queue" aria-label="Draft review queue">
                    {selectedBatch.drafts.map((draft) => (
                      <div
                        key={draft.id}
                        className={`draft-queue-row${
                          selectedDraft?.id === draft.id ? " draft-queue-row--active" : ""
                        }`}
                      >
                        <input
                          type="checkbox"
                          aria-label={`Select ${draft.business_name} for approval`}
                          checked={approvalIds.includes(draft.id)}
                          disabled={draft.review_status !== "pending_review"}
                          onChange={() => toggleApproval(draft.id)}
                        />
                        <button
                          type="button"
                          onClick={() => setSelectedDraftId(draft.id)}
                        >
                          <span>
                            <strong>{draft.business_name}</strong>
                            <small>{draft.current_revision.subject}</small>
                          </span>
                          <span className={`status-badge${reviewTone(draft)}`}>
                            {reviewLabel(draft)}
                          </span>
                          <ChevronRight size={16} aria-hidden="true" />
                        </button>
                      </div>
                    ))}
                  </div>
                  {selectedDraft ? (
                    <DraftEditor
                      key={`${selectedDraft.id}-${selectedDraft.current_version}-${selectedDraft.review_status}-${selectedDraft.sync_status}`}
                      draft={selectedDraft}
                    />
                  ) : null}
                </div>
              </>
            )}
          </section>
        </TaskPanel>
      )}
    </>
  );
}
