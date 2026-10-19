import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Copy,
  MailCheck,
  Megaphone,
  PackageCheck,
  PencilLine,
  Play,
  RefreshCw,
  Send,
  Star,
  Users,
  type LucideIcon,
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
  Collapsible,
  EmptyState,
  HelpTip,
  MetricCard,
  PageHeader,
  SkeletonRows,
} from "./DesignSystem";

interface TodayAction {
  id: string;
  tone: "error" | "warning" | "accent" | "success" | "neutral";
  icon: LucideIcon;
  title: string;
  detail: string;
  actionLabel: string;
  onAction: () => void;
  disabled?: boolean;
}

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
    goToPipeline: onOpenPipeline,
    goToCampaigns: onOpenCampaigns,
    goToLeads: onOpenLeads,
    goToLeadsNeedingReview: onOpenLeadsNeedingReview,
    goToCatalogue: onOpenCatalogue,
    goToEmailDrafts: onOpenEmailDrafts,
    runWeeklyOutreach: onRunWeekly,
    retryWeeklyOutreach: onRetryWeekly,
  } = useWorkspaceActions();
  const weekStart = mondayIso();
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
  const runSummary =
    enabledCampaigns.length === 0
      ? "Weekly outreach is off"
      : activeRuns.length > 0
        ? `${activeRuns.length} running now`
        : caughtUp
          ? "You are caught up for this week"
          : `${completedRuns.length} of ${enabledCampaigns.length} completed`;
  const followUpsDue = (summary?.due_today ?? 0) + (summary?.overdue ?? 0);
  // Same count as the sidebar badge: every shortlist entry still awaiting a decision.
  const shortlistToDecide = shortlists.reduce(
    (total, shortlist) => total + shortlist.items.filter((item) => item.decision === "recommended").length,
    0,
  );
  const reviewRequired = summary?.review_required ?? 0;
  const nextMonday = new Date(`${weekStart}T00:00:00`);
  nextMonday.setDate(nextMonday.getDate() + 7);
  const today = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long" }).format(new Date());

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

  const plural = (count: number, one: string, many: string) => (count === 1 ? one : many);

  // What needs the operator, most urgent first. Each card has exactly one way forward.
  const todayActions: TodayAction[] = [
    failedRuns.length > 0 && {
      id: "failed",
      tone: "error",
      icon: AlertTriangle,
      title: `${failedRuns.length} ${plural(failedRuns.length, "campaign", "campaigns")} stopped`,
      detail: "The others carried on. Retry it from the weekly runs below.",
      actionLabel: "See campaigns",
      onAction: onOpenCampaigns,
    },
    dueCampaigns.length > 0 && {
      id: "due",
      tone: "accent",
      icon: Play,
      title: `${dueCampaigns.length} ${plural(dueCampaigns.length, "campaign is", "campaigns are")} due to run`,
      detail: "Finds and scores leads, then prepares drafts. Nothing is sent.",
      actionLabel: "Run due campaigns",
      onAction: confirmAndRunDueCampaigns,
      disabled: busy,
    },
    pendingDrafts > 0 && {
      id: "drafts",
      tone: "warning",
      icon: MailCheck,
      title: `${pendingDrafts} ${plural(pendingDrafts, "draft", "drafts")} to approve`,
      detail: "Edit, approve or reject each one.",
      actionLabel: "Review drafts",
      onAction: onOpenEmailDrafts,
    },
    approvedDrafts > 0 && {
      id: "approved",
      tone: "success",
      icon: Send,
      title: `${approvedDrafts} approved ${plural(approvedDrafts, "email", "emails")} ready for Zoho`,
      detail: "Open each one in Zoho and send it yourself.",
      actionLabel: "Open approved",
      onAction: onOpenEmailDrafts,
    },
    openedInZoho > 0 && {
      id: "confirm",
      tone: "neutral",
      icon: CheckCircle2,
      title: `${openedInZoho} ${plural(openedInZoho, "email", "emails")} to mark as sent`,
      detail: "Confirm only once it has left Zoho.",
      actionLabel: "Confirm sent",
      onAction: onOpenEmailDrafts,
    },
    followUpsDue > 0 && {
      id: "follow-ups",
      tone: (summary?.overdue ?? 0) > 0 ? "warning" : "accent",
      icon: CalendarClock,
      title: `${followUpsDue} ${plural(followUpsDue, "follow-up", "follow-ups")} due`,
      detail: (summary?.overdue ?? 0) > 0 ? `${summary?.overdue} overdue.` : "Due today.",
      actionLabel: "Open pipeline",
      onAction: onOpenPipeline,
    },
    shortlistToDecide > 0 && {
      id: "shortlist",
      tone: "accent",
      icon: Star,
      title: `${shortlistToDecide} shortlisted ${plural(shortlistToDecide, "lead", "leads")} to decide`,
      detail: "Approve, defer or dismiss each recommended lead.",
      actionLabel: "Open shortlist",
      onAction: onOpenShortlist,
    },
    reviewRequired > 0 && {
      id: "review",
      tone: "neutral",
      icon: Users,
      title: `${reviewRequired} ${plural(reviewRequired, "lead needs", "leads need")} review`,
      detail: missingContext > 0 ? `${missingContext} missing context from this week's runs.` : "Check the details before contacting them.",
      actionLabel: "Review leads",
      onAction: onOpenLeadsNeedingReview,
    },
    duplicateReviews > 0 && {
      id: "duplicates",
      tone: "neutral",
      icon: Copy,
      title: `${duplicateReviews} possible ${plural(duplicateReviews, "duplicate", "duplicates")}`,
      detail: "A run found a business that may already be a lead.",
      actionLabel: "Check in Campaigns",
      onAction: onOpenCampaigns,
    },
  ].filter((action): action is TodayAction => Boolean(action));

  return (
    <>
      <PageHeader title="Today" description={`${today} · week beginning ${formatDate(weekStart)}`} />

      <section className="today-actions" aria-labelledby="today-actions-heading">
        <h2 id="today-actions-heading" className="visually-hidden">Needs you</h2>
        {loading ? (
          <SkeletonRows rows={3} label="Loading what needs you" />
        ) : todayActions.length === 0 ? (
          <div className="today-clear">
            <CheckCircle2 size={28} aria-hidden="true" />
            <div>
              <strong>You're up to date</strong>
              <p>
                {enabledCampaigns.length > 0
                  ? `The next weekly check runs on ${formatDate(nextMonday.toISOString().slice(0, 10))}.`
                  : "Turn on weekly outreach in a campaign to have drafts prepared each week."}
              </p>
            </div>
          </div>
        ) : (
          <ul className="today-action-list">
            {todayActions.map((action) => {
              const Icon = action.icon;
              return (
                <li key={action.id} className={`today-action today-action--${action.tone}`}>
                  <span className="today-action__icon" aria-hidden="true"><Icon size={20} /></span>
                  <div className="today-action__copy">
                    <strong>{action.title}</strong>
                    <p>{action.detail}</p>
                  </div>
                  <button
                    type="button"
                    className={action.tone === "accent" || action.tone === "warning" || action.tone === "error" ? "primary-action" : "secondary-action"}
                    disabled={action.disabled}
                    onClick={action.onAction}
                  >
                    {action.actionLabel} <ArrowRight size={16} aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <div className="today-grid">
        <section className="records-panel today-panel" aria-labelledby="today-week-heading">
          <div className="records-heading">
            <div><h3 id="today-week-heading">This week</h3><p>From found to sent</p></div>
          </div>
          <ol className="today-funnel">
            {[
              ["Found", discovered],
              ["Scored", scored],
              ["Shortlisted", shortlisted],
              ["Drafted", draftsCreated],
              ["Sent", sentThisWeek],
            ].map(([label, value]) => (
              <li key={String(label)}><strong>{value}</strong><span>{label}</span></li>
            ))}
          </ol>
          <div className="today-pipeline" aria-label="Pipeline by stage group">
            {PIPELINE_GROUPS.map((group) => {
              const count = group.stages.reduce(
                (total, stage) => total + (summary?.pipeline[stage] ?? 0),
                0,
              );
              return (
                <div key={group.label}><strong>{count}</strong><span>{group.label}</span></div>
              );
            })}
          </div>
        </section>

        <section className="records-panel today-panel" aria-labelledby="today-follow-ups-heading">
          <div className="records-heading">
            <div><h3 id="today-follow-ups-heading">Coming up</h3><p>Next follow-ups by due date</p></div>
            <span>{summary?.open_follow_ups ?? due.length} open</span>
          </div>
          {due.length === 0 ? (
            <EmptyState title="No follow-ups planned" description="Add one from a lead in Pipeline." />
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
        </section>
      </div>

      <Collapsible
        rememberKey="today-weekly-runs"
        title="Weekly runs"
        summary={runSummary}
        icon={RefreshCw}
        actions={
          <>
            <span className="weekly-capacity-label">
              {draftsCreated}/{settings?.weekly_outreach_global_limit ?? 20} drafts this week
              <HelpTip label="About weekly draft capacity">
                This workspace-wide safety limit is applied after a shared lead has been assigned
                to its strongest campaign. Change it in Settings.
              </HelpTip>
            </span>
            <HelpTip label="How the weekly check works">
              While the app is open, enabled campaigns refresh once each week and prepare local
              drafts only. If the app was closed at the start of the week, it catches up when you
              next open it. Every draft still needs your approval, and nothing is sent automatically.
            </HelpTip>
          </>
        }
      >
        {enabledCampaigns.length === 0 ? (
          <EmptyState
            title="No automated campaigns"
            description="Open a campaign, choose its weekly template and turn on weekly outreach."
            action={
              <button className="secondary-action" type="button" onClick={onOpenCampaigns}>
                Set up in Campaigns
              </button>
            }
          />
        ) : (
          <div className="weekly-campaign-list">
            <p className="weekly-campaign-list__summary">{runSummary}</p>
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
            {dueCampaigns.length === 0 && enabledCampaigns.length > 0 ? (
              <button
                className="tertiary-action"
                type="button"
                disabled={busy}
                onClick={() => void onRunWeekly()}
              >
                <RefreshCw size={15} aria-hidden="true" /> Check again now
              </button>
            ) : null}
          </div>
        )}
      </Collapsible>

      <section className="today-totals" aria-label="Business overview">
        <MetricCard label="Active campaigns" value={summary?.active_campaigns ?? 0} detail={`${campaigns.length} total`} icon={Megaphone} onSelect={onOpenCampaigns} />
        <MetricCard label="Leads" value={summary?.leads ?? leads.length} detail={activeHolds > 0 ? `${activeHolds} on hold` : "On this computer"} icon={Users} onSelect={onOpenLeads} />
        <MetricCard label="Active products" value={summary?.products ?? 0} detail="In the catalogue" icon={PackageCheck} onSelect={onOpenCatalogue} />
        <MetricCard
          label="Draft edit rate"
          value={
            summary?.average_draft_edit_ratio === null ||
            summary?.average_draft_edit_ratio === undefined
              ? "No data"
              : `${Math.round(summary.average_draft_edit_ratio * 100)}%`
          }
          detail={
            summary?.approved_drafts_measured
              ? `How much you rewrite before approving, over ${summary.approved_drafts_measured} drafts. Under 25% means the local model is doing the job.`
              : "Approve a draft to start measuring."
          }
          icon={PencilLine}
        />
      </section>
    </>
  );
}
