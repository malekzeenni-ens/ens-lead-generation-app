import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Megaphone,
  PackageCheck,
  ShieldCheck,
  Star,
  Users,
} from "lucide-react";

import { PIPELINE_GROUPS, formatDate, humanize, openFollowUps } from "../domain";
import type { Campaign, Lead, OperationsSummary, Shortlist } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { EmptyState, LoadingState, MetricCard, PageHeader, SectionHeading } from "./DesignSystem";

interface DashboardWorkspaceProps {
  campaigns: Campaign[];
  leads: Lead[];
  summary: OperationsSummary | null;
  shortlists: Shortlist[];
}

export function DashboardWorkspace({
  campaigns,
  leads,
  summary,
  shortlists,
}: DashboardWorkspaceProps) {
  const {
    loading,
    goToCreateCampaign: onCreateCampaign,
    manageLead: onManageLead,
    goToShortlist: onOpenShortlist,
    goToCampaigns: onOpenCampaigns,
    goToLeads: onOpenLeads,
    goToLeadsNeedingReview: onOpenLeadsNeedingReview,
    goToCatalogue: onOpenCatalogue,
  } = useWorkspaceActions();
  const due = openFollowUps(leads).slice(0, 5);
  const latestShortlist = shortlists[0] ?? null;
  const activeShortlistItems = latestShortlist?.items
    .filter((item) => ["recommended", "approved"].includes(item.decision))
    .slice(0, 5) ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Local operations"
        title="Lead intelligence dashboard"
        description="Manage prospects from verified entry through follow-up and outcome while every action remains local and under human control."
        action={
          <button className="primary-action" type="button" onClick={onCreateCampaign}>
            <Megaphone size={18} aria-hidden="true" />
            New campaign
          </button>
        }
      />

      <section className="metrics-grid" aria-label="Workspace summary">
        <MetricCard
          label="Active campaigns"
          value={summary?.active_campaigns ?? campaigns.filter((item) => item.status === "active").length}
          detail={`${summary?.campaigns ?? campaigns.length} total`}
          icon={Megaphone}
          onSelect={onOpenCampaigns}
        />
        <MetricCard
          label="Leads"
          value={summary?.leads ?? leads.length}
          detail="Locally stored"
          icon={Users}
          onSelect={onOpenLeads}
        />
        <MetricCard
          label="Active products"
          value={summary?.products ?? 0}
          detail="Matching catalogue"
          icon={PackageCheck}
          onSelect={onOpenCatalogue}
        />
        <MetricCard
          label="Scored leads"
          value={summary?.scored_leads ?? leads.filter((lead) => lead.current_score !== null).length}
          detail={`${summary?.shortlisted_this_week ?? 0} shortlisted`}
          icon={Star}
          onSelect={onOpenLeads}
        />
        <MetricCard
          label="Needs review"
          value={summary?.review_required ?? 0}
          detail={`${summary?.suppressed_leads ?? 0} suppressed`}
          icon={AlertTriangle}
          tone={(summary?.review_required ?? 0) > 0 ? "warning" : "default"}
          onSelect={onOpenLeadsNeedingReview}
        />
      </section>

      <section className="workspace-section" aria-labelledby="operations-heading">
        <SectionHeading
          id="operations-heading"
          eyebrow="Today"
          title="Operating queue"
          description="The next manual actions and a simplified view of the pipeline."
          icon={CalendarClock}
        />

        <div className="dashboard-grid">
          <div className="records-panel">
            <div className="records-heading">
              <div>
                <h3>Weekly shortlist</h3>
                <p>Strongest controlled recommendations</p>
              </div>
              <button className="tertiary-action" type="button" onClick={onOpenShortlist}>Open</button>
            </div>
            {loading ? (
              <LoadingState label="Loading weekly shortlist" />
            ) : activeShortlistItems.length === 0 ? (
              <EmptyState
                title="No weekly shortlist"
                description="Generate one after scoring campaign leads."
              />
            ) : (
              <div className="action-list">
                {activeShortlistItems.map((item) => (
                  <button type="button" className="action-row" key={item.id} onClick={() => onManageLead(item.lead_id)}>
                    <span className="record-icon" aria-hidden="true"><Star size={17} /></span>
                    <span><strong>{item.business_name}</strong><small>{item.score}/100 · {humanize(item.decision)}</small></span>
                    <ArrowRight size={17} aria-hidden="true" />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="records-panel">
            <div className="records-heading">
              <div>
                <h3>Open follow-ups</h3>
                <p>Ordered by due date</p>
              </div>
              <span>{summary?.open_follow_ups ?? due.length} open</span>
            </div>
            {loading ? (
              <LoadingState label="Loading follow-ups" />
            ) : due.length === 0 ? (
              <EmptyState
                title="No follow-ups due"
                description="Create the next action from a lead’s pipeline workspace."
              />
            ) : (
              <div className="action-list">
                {due.map(({ lead, followUp }) => (
                  <button
                    type="button"
                    className="action-row"
                    key={followUp.id}
                    onClick={() => onManageLead(lead.id)}
                  >
                    <span className="record-icon" aria-hidden="true">
                      <CalendarClock size={17} />
                    </span>
                    <span>
                      <strong>{lead.business_name}</strong>
                      <small>{humanize(followUp.follow_up_type)} · {formatDate(followUp.due_date)}</small>
                    </span>
                    <ArrowRight size={17} aria-hidden="true" />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="records-panel">
            <div className="records-heading">
              <div>
                <h3>Pipeline summary</h3>
                <p>Grouped for a low-volume workflow</p>
              </div>
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
                    <span aria-hidden="true">
                      {group.label === "Closed" ? <CheckCircle2 size={18} /> : <ShieldCheck size={18} />}
                    </span>
                    <div>
                      <strong>{count}</strong>
                      <p>{group.label}</p>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
