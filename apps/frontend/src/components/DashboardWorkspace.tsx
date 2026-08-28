import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  CirclePause,
  MailCheck,
  Megaphone,
  PackageCheck,
  Play,
  RefreshCw,
  ShieldCheck,
  Star,
  Users,
} from "lucide-react";

import {
  PIPELINE_GROUPS,
  formatDate,
  humanize,
  mondayIso,
  openFollowUps,
} from "../domain";
import type {
  Campaign,
  CampaignRun,
  Lead,
  OperationsSummary,
  OutreachBatch,
  Shortlist,
  WorkspaceSettings,
} from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import {
  EmptyState,
  GuidanceNote,
  HelpTip,
  LoadingState,
  MetricCard,
  PageHeader,
  SectionHeading,
} from "./DesignSystem";

interface DashboardWorkspaceProps {
  campaigns: Campaign[];
  campaignRuns: CampaignRun[];
  leads: Lead[];
  summary: OperationsSummary | null;
  settings: WorkspaceSettings | null;
  shortlists: Shortlist[];
  outreachBatches: OutreachBatch[];
}

function runStatus(run: CampaignRun | undefined): string {
  if (!run) return "Due";
  if (run.status === "failed") return "Failed";
  if (["queued", "running"].includes(run.status)) return humanize(run.phase);
  if (run.status === "completed_with_warnings") return "Needs attention";
  if (run.status === "cancelled") return "Cancelled";
  return "Completed";
}

function runTone(run: CampaignRun | undefined): string {
  if (!run || run.status === "failed" || run.status === "completed_with_warnings") {
    return " status-badge--warning";
  }
  if (run.status === "completed") return " status-badge--success";
  return "";
}

function runStatusDescription(run: CampaignRun | undefined): string {
  if (!run) {
    return "This campaign has not run in the current week. It will run on the next weekly check.";
  }
  if (run.status === "failed") {
    return "This campaign stopped safely. Other campaigns continued and this run can be retried.";
  }
  if (["queued", "running"].includes(run.status)) {
    return `The campaign is currently in the ${humanize(run.phase).toLocaleLowerCase()} stage.`;
  }
  if (run.status === "completed_with_warnings") {
    return "The campaign finished, but one or more leads or provider checks need attention.";
  }
  if (run.status === "cancelled") {
    return "This campaign run was cancelled before weekly preparation completed.";
  }
  return "The campaign completed its current-week refresh and draft preparation.";
}

export function DashboardWorkspace({
  campaigns,
  campaignRuns,
  leads,
  summary,
  settings,
  shortlists,
  outreachBatches,
}: DashboardWorkspaceProps) {
  const {
    loading,
    busy,
    manageLead: onManageLead,
    goToShortlist: onOpenShortlist,
    goToCampaigns: onOpenCampaigns,
    goToLeads: onOpenLeads,
    goToLeadsNeedingReview: onOpenLeadsNeedingReview,
    goToCatalogue: onOpenCatalogue,
    goToEmailDrafts: onOpenEmailDrafts,
    runWeeklyOutreach: onRunWeekly,
    retryWeeklyOutreach: onRetryWeekly,
  } = useWorkspaceActions();
  const weekStart = mondayIso();
  const weekday = new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(new Date());
  const enabledCampaigns = campaigns.filter(
    (campaign) => campaign.status === "active" && campaign.weekly_outreach_enabled,
  );
  const weeklyRuns = campaignRuns.filter((run) => run.week_start === weekStart);
  const runByCampaign = new Map(
    weeklyRuns.map((run) => [run.campaign_id, run] as const),
  );
  const dueCampaigns = enabledCampaigns.filter((campaign) => !runByCampaign.has(campaign.id));
  const activeRuns = weeklyRuns.filter((run) => ["queued", "running"].includes(run.status));
  const completedRuns = weeklyRuns.filter((run) =>
    ["completed", "completed_with_warnings"].includes(run.status),
  );
  const failedRuns = weeklyRuns.filter((run) => run.status === "failed");
  const draftsCreated = weeklyRuns.reduce(
    (total, run) => total + (run.metrics.drafts_created ?? 0),
    0,
  );
  const attentionTotal = weeklyRuns.reduce(
    (total, run) => total + (run.metrics.attention_required ?? 0),
    0,
  );
  const missingContext = weeklyRuns.reduce(
    (total, run) => total + (run.metrics.missing_context ?? 0),
    0,
  );
  const duplicateReviews = weeklyRuns.reduce(
    (total, run) =>
      total + run.candidates.filter((candidate) => candidate.status === "review_required").length,
    0,
  );
  const activeHolds = leads.filter((lead) => lead.outreach_hold_reason).length;
  const pendingDrafts = outreachBatches.reduce(
    (total, batch) => total + batch.pending_count,
    0,
  );
  const approvedDrafts = outreachBatches.reduce(
    (total, batch) => total + batch.approved_count,
    0,
  );
  const openedInZoho = outreachBatches.reduce(
    (total, batch) =>
      total + batch.drafts.filter((draft) => draft.sync_status === "opened_in_zoho").length,
    0,
  );
  const sentThisWeek = outreachBatches.reduce(
    (total, batch) =>
      total +
      batch.drafts.filter(
        (draft) => draft.sync_status === "user_confirmed_sent" && draft.updated_at >= weekStart,
      ).length,
    0,
  );
  const due = openFollowUps(leads).slice(0, 5);
  const latestShortlist = shortlists.find((shortlist) => shortlist.week_start === weekStart) ?? null;
  const activeShortlistItems =
    latestShortlist?.items
      .filter((item) => ["recommended", "approved"].includes(item.decision))
      .slice(0, 5) ?? [];
  const discovered = weeklyRuns.reduce(
    (total, run) => total + (run.metrics.discovered ?? 0),
    0,
  );
  const scored = weeklyRuns.reduce(
    (total, run) => total + (run.metrics.leads_scored ?? 0),
    0,
  );
  const shortlisted = weeklyRuns.reduce(
    (total, run) => total + (run.metrics.shortlist_selected ?? 0),
    0,
  );

  const caughtUp =
    enabledCampaigns.length > 0 &&
    dueCampaigns.length === 0 &&
    activeRuns.length === 0 &&
    failedRuns.length === 0;
  const bannerTitle =
    enabledCampaigns.length === 0
      ? "Weekly outreach is not enabled"
      : activeRuns.length > 0
        ? `${activeRuns.length} campaign${activeRuns.length === 1 ? " is" : "s are"} running`
        : failedRuns.length > 0
          ? `${failedRuns.length} campaign${failedRuns.length === 1 ? " needs" : "s need"} retrying`
          : caughtUp
            ? "You are caught up for this week"
            : `${dueCampaigns.length} campaign${dueCampaigns.length === 1 ? " is" : "s are"} due`;
  const bannerDetail =
    enabledCampaigns.length === 0
      ? "Enable a template and provider from a campaign to start first-open weekly preparation."
      : `${weekday} check for the week beginning ${formatDate(weekStart)} · ${completedRuns.length} of ${enabledCampaigns.length} completed`;

  function confirmAndRunDueCampaigns(): void {
    const campaignCount = dueCampaigns.length;
    if (campaignCount === 0) return;
    const externalProviderCount = dueCampaigns.filter(
      (campaign) => campaign.weekly_outreach_provider !== "scoring",
    ).length;
    const providerDetail =
      externalProviderCount > 0
        ? `${externalProviderCount} configured campaign${externalProviderCount === 1 ? " may" : "s may"} call an external discovery provider.`
        : "These campaigns will refresh existing lead scores without calling a discovery provider.";
    const confirmed = window.confirm(
      `Run ${campaignCount} due campaign${campaignCount === 1 ? "" : "s"} now?\n\n${providerDetail}\n\nAutomation can prepare up to ${settings?.weekly_outreach_global_limit ?? 20} local drafts across all campaigns. No email will be sent.`,
    );
    if (confirmed) void onRunWeekly();
  }

  return (
    <>
      <PageHeader
        eyebrow="Weekly control centre"
        title="Lead intelligence dashboard"
        description="See what ran, what needs you and which approved emails are ready for Zoho."
        action={
          dueCampaigns.length > 0 ? (
            <button
              className="primary-action"
              type="button"
              disabled={busy}
              title="Refresh every due enabled campaign and prepare local drafts after confirmation"
              onClick={confirmAndRunDueCampaigns}
            >
              <Play size={18} aria-hidden="true" /> Run due campaigns
            </button>
          ) : pendingDrafts > 0 ? (
            <button className="primary-action" type="button" onClick={onOpenEmailDrafts}>
              <MailCheck size={18} aria-hidden="true" /> Review drafts
            </button>
          ) : (
            <button
              className="secondary-action"
              type="button"
              disabled={busy || enabledCampaigns.length === 0}
              onClick={() => void onRunWeekly()}
            >
              <RefreshCw size={18} aria-hidden="true" /> Check weekly automation
            </button>
          )
        }
      />

      <GuidanceNote title="How the weekly check works">
        On the first app opening each week, enabled campaigns refresh sequentially and prepare
        local drafts only. Opening later in the week catches up once; every draft still requires
        your edit and approval, and nothing is sent automatically.
      </GuidanceNote>

      <section
        className={`weekly-status-banner${caughtUp ? " weekly-status-banner--success" : ""}`}
      >
        <div className="weekly-status-banner__icon" aria-hidden="true">
          {caughtUp ? <CheckCircle2 size={22} /> : <CalendarClock size={22} />}
        </div>
        <div>
          <span className="eyebrow">Week beginning {formatDate(weekStart)}</span>
          <h2>{bannerTitle}</h2>
          <p>{bannerDetail}</p>
        </div>
        <div className="weekly-capacity">
          <strong>{draftsCreated}/{settings?.weekly_outreach_global_limit ?? 20}</strong>
          <span className="weekly-capacity-label">
            weekly draft capacity
            <HelpTip label="About weekly draft capacity">
              This workspace-wide safety limit is applied after a shared lead has been assigned
              to its strongest campaign. Change it in Settings.
            </HelpTip>
          </span>
        </div>
      </section>

      <section
        className="metrics-grid metrics-grid--operations"
        aria-label="Weekly outreach summary"
      >
        <MetricCard
          label="Campaign progress"
          value={`${completedRuns.length}/${enabledCampaigns.length}`}
          detail={activeRuns.length > 0 ? `${activeRuns.length} running` : `${dueCampaigns.length} due`}
          icon={Megaphone}
          onSelect={onOpenCampaigns}
        />
        <MetricCard
          label="Draft review"
          value={pendingDrafts}
          detail={approvedDrafts > 0 ? `${approvedDrafts} approved for Zoho` : "Waiting for your decision"}
          icon={MailCheck}
          tone={pendingDrafts > 0 ? "warning" : "default"}
          onSelect={onOpenEmailDrafts}
        />
        <MetricCard
          label="Needs attention"
          value={attentionTotal + duplicateReviews + failedRuns.length}
          detail={`${missingContext} missing Context`}
          icon={AlertTriangle}
          tone={attentionTotal + duplicateReviews + failedRuns.length > 0 ? "warning" : "default"}
          onSelect={onOpenLeadsNeedingReview}
        />
        <MetricCard
          label="Sent this week"
          value={sentThisWeek}
          detail={openedInZoho > 0 ? `${openedInZoho} awaiting confirmation` : "User confirmed"}
          icon={CheckCircle2}
          onSelect={onOpenEmailDrafts}
        />
      </section>

      <section className="workspace-section" aria-labelledby="weekly-automation-heading">
        <SectionHeading
          id="weekly-automation-heading"
          eyebrow="Multiple campaigns"
          title="Weekly automation"
          description="Campaigns run sequentially. A problem in one campaign does not stop the rest."
          icon={RefreshCw}
          count={enabledCampaigns.length}
        />
        {loading ? (
          <LoadingState label="Loading weekly automation" />
        ) : enabledCampaigns.length === 0 ? (
          <EmptyState
            title="No automated campaigns"
            description="Open a campaign, choose its weekly template and enable automatic preparation."
            action={
              <button className="primary-action" type="button" onClick={onOpenCampaigns}>
                Configure campaigns
              </button>
            }
          />
        ) : (
          <div className="weekly-campaign-list">
            {enabledCampaigns.map((campaign) => {
              const run = runByCampaign.get(campaign.id);
              const runDrafts = run?.metrics.drafts_created ?? 0;
              const runAttention = run?.metrics.attention_required ?? 0;
              return (
                <article className="weekly-campaign-row" key={campaign.id}>
                  <div>
                    <strong>{campaign.name}</strong>
                    <small>
                      {humanize(campaign.weekly_outreach_provider)} · up to{" "}
                      {campaign.weekly_shortlist_size} drafts
                    </small>
                  </div>
                  <span
                    className={`status-badge${runTone(run)}`}
                    title={runStatusDescription(run)}
                    aria-label={`${runStatus(run)}: ${runStatusDescription(run)}`}
                  >
                    {runStatus(run)}
                  </span>
                  <div className="weekly-campaign-result">
                    <strong>{runDrafts} drafts</strong>
                    <small>{runAttention > 0 ? `${runAttention} need attention` : "No blockers"}</small>
                  </div>
                  {run?.status === "failed" ? (
                    <button
                      className="secondary-action"
                      type="button"
                      disabled={busy}
                      title="Retry only this failed campaign; other completed campaigns will not run again"
                      onClick={() => void onRetryWeekly(run.id)}
                    >
                      Retry
                    </button>
                  ) : run?.outreach_batch_id ? (
                    <button className="tertiary-action" type="button" onClick={onOpenEmailDrafts}>
                      Review <ArrowRight size={15} aria-hidden="true" />
                    </button>
                  ) : (
                    <button className="tertiary-action" type="button" onClick={onOpenCampaigns}>
                      View <ArrowRight size={15} aria-hidden="true" />
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="workspace-section" aria-labelledby="action-queue-heading">
        <SectionHeading
          id="action-queue-heading"
          eyebrow="Your decisions"
          title="Action queue"
          description="Automation prepares the work; approval and sending remain with you."
          icon={ShieldCheck}
        />
        <div className="dashboard-grid dashboard-grid--actions">
          <div className="records-panel">
            <div className="records-heading">
              <div><h3>Your action queue</h3><p>Ordered by outreach stage</p></div>
            </div>
            <div className="action-list">
              <button type="button" className="action-row" onClick={onOpenEmailDrafts}>
                <span className="record-icon"><MailCheck size={17} /></span>
                <span><strong>{pendingDrafts} drafts to review</strong><small>Edit, approve or reject</small></span>
                <ArrowRight size={17} />
              </button>
              <button type="button" className="action-row" onClick={onOpenEmailDrafts}>
                <span className="record-icon"><CheckCircle2 size={17} /></span>
                <span><strong>{approvedDrafts} approved for Zoho</strong><small>Open and send manually</small></span>
                <ArrowRight size={17} />
              </button>
              <button type="button" className="action-row" onClick={onOpenEmailDrafts}>
                <span className="record-icon"><CalendarClock size={17} /></span>
                <span><strong>{openedInZoho} awaiting sent confirmation</strong><small>Confirm only after sending</small></span>
                <ArrowRight size={17} />
              </button>
            </div>
          </div>

          <div className="records-panel">
            <div className="records-heading">
              <div><h3>Needs attention</h3><p>Grouped by the next fix</p></div>
            </div>
            <div className="attention-summary">
              <button type="button" onClick={onOpenLeadsNeedingReview}><strong>{missingContext}</strong><span>Missing Context</span></button>
              <button type="button" onClick={onOpenCampaigns}><strong>{duplicateReviews}</strong><span>Possible duplicates</span></button>
              <button type="button" onClick={onOpenLeads}><strong>{activeHolds}</strong><span>Outreach holds</span></button>
              <button type="button" onClick={onOpenCampaigns}><strong>{failedRuns.length}</strong><span>Failed campaigns</span></button>
            </div>
          </div>
        </div>
      </section>

      <section className="workspace-section weekly-funnel" aria-labelledby="weekly-results-heading">
        <SectionHeading
          id="weekly-results-heading"
          eyebrow="This week's results"
          title="From discovery to sending"
          description="A simple view of the current week's controlled funnel."
          icon={Star}
        />
        <div className="weekly-funnel__steps">
          {[
            ["Discovered", discovered],
            ["Scored", scored],
            ["Shortlisted", shortlisted],
            ["Drafts", draftsCreated],
            ["Sent", sentThisWeek],
          ].map(([label, value], index) => (
            <div key={String(label)}>
              <strong>{value}</strong><span>{label}</span>
              {index < 4 ? <ArrowRight size={17} aria-hidden="true" /> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="workspace-section" aria-labelledby="operations-heading">
        <SectionHeading
          id="operations-heading"
          eyebrow="Supporting work"
          title="Shortlist, follow-ups and pipeline"
          description="The existing operational views remain available beneath the weekly control centre."
          icon={CalendarClock}
        />
        <div className="dashboard-grid">
          <div className="records-panel">
            <div className="records-heading">
              <div><h3>Weekly shortlist</h3><p>Strongest controlled recommendations</p></div>
              <button className="tertiary-action" type="button" onClick={onOpenShortlist}>Open</button>
            </div>
            {activeShortlistItems.length === 0 ? (
              <EmptyState title="No weekly shortlist" description="Automation will prepare one after scoring." />
            ) : (
              <div className="action-list">
                {activeShortlistItems.map((item) => (
                  <button type="button" className="action-row" key={item.id} onClick={() => onManageLead(item.lead_id)}>
                    <span className="record-icon"><Star size={17} /></span>
                    <span><strong>{item.business_name}</strong><small>{item.score}/100 · {humanize(item.decision)}</small></span>
                    <ArrowRight size={17} />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="records-panel">
            <div className="records-heading">
              <div><h3>Open follow-ups</h3><p>Ordered by due date</p></div>
              <span>{summary?.open_follow_ups ?? due.length} open</span>
            </div>
            {due.length === 0 ? (
              <EmptyState title="No follow-ups due" description="There are no manual follow-ups in the current window." />
            ) : (
              <div className="action-list">
                {due.map(({ lead, followUp }) => (
                  <button type="button" className="action-row" key={followUp.id} onClick={() => onManageLead(lead.id)}>
                    <span className="record-icon"><CalendarClock size={17} /></span>
                    <span><strong>{lead.business_name}</strong><small>{humanize(followUp.follow_up_type)} · {formatDate(followUp.due_date)}</small></span>
                    <ArrowRight size={17} />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="records-panel">
            <div className="records-heading">
              <div><h3>Pipeline summary</h3><p>Grouped for a low-volume workflow</p></div>
              <span>{leads.length} leads</span>
            </div>
            <div className="pipeline-summary">
              {PIPELINE_GROUPS.map((group) => {
                const count = group.stages.reduce(
                  (total, stage) => total + (summary?.pipeline[stage] ?? 0),
                  0,
                );
                return (
                  <article key={group.label}>
                    <span>{group.label === "Closed" ? <CheckCircle2 size={18} /> : <ShieldCheck size={18} />}</span>
                    <div><strong>{count}</strong><p>{group.label}</p></div>
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section className="metrics-grid metrics-grid--compact" aria-label="Business overview">
        <MetricCard label="Active campaigns" value={summary?.active_campaigns ?? 0} detail={`${campaigns.length} total`} icon={Megaphone} onSelect={onOpenCampaigns} />
        <MetricCard label="Leads" value={summary?.leads ?? leads.length} detail="Locally stored" icon={Users} onSelect={onOpenLeads} />
        <MetricCard label="Active products" value={summary?.products ?? 0} detail="Matching catalogue" icon={PackageCheck} onSelect={onOpenCatalogue} />
        <MetricCard label="Open follow-ups" value={summary?.open_follow_ups ?? 0} detail={`${summary?.due_this_week ?? 0} due soon`} icon={CirclePause} onSelect={onOpenLeads} />
      </section>
    </>
  );
}
