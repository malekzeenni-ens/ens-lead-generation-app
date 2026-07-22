import { Ban, Link2, RefreshCw, UserPlus } from "lucide-react";
import { useMemo } from "react";

import { usePagination } from "../pagination";
import type { AutomationCapabilities, Campaign, CampaignRun } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { runProviderLabel } from "./campaignShared";
import { EmptyState, LoadingState, Pagination, SectionHeading, StatGrid } from "./DesignSystem";

interface CampaignAutomationTabProps {
  campaigns: Campaign[];
  campaignRuns: CampaignRun[];
  capabilities: AutomationCapabilities | null;
}

export function CampaignAutomationTab({
  campaigns,
  campaignRuns,
  capabilities,
}: CampaignAutomationTabProps) {
  const {
    loading,
    busy,
    runAllCampaigns: onRunAll,
    cancelCampaignRun: onCancelRun,
    decideDiscoveryCandidate: onCandidateDecision,
  } = useWorkspaceActions();
  const runPages = usePagination(campaignRuns, 5);
  const reviewCandidates = useMemo(
    () =>
      campaignRuns.flatMap((run) =>
        run.candidates
          .filter((candidate) => ["review_required", "discovered"].includes(candidate.status))
          .map((candidate) => ({ candidate, campaignName: run.campaign_name })),
      ),
    [campaignRuns],
  );
  const candidatePages = usePagination(reviewCandidates, 5);

  return (
    <section className="workspace-section" aria-labelledby="automation-heading">
      <SectionHeading
        id="automation-heading"
        eyebrow="Operator-triggered automation"
        title="Discover, score and prepare"
        description="Choose exactly one discovery provider per run. That source completes duplicate checks before deterministic scoring, product matching and shortlist preparation."
        icon={RefreshCw}
        count={campaignRuns.length}
      />

      <div className="automation-toolbar">
        <div>
          <strong>Run active campaigns by provider</strong>
          <p>
            Google Places discovers new businesses. Instagram refreshes professional profiles
            already saved to leads. Public registries automatically checks sources relevant to
            each campaign (e.g. FHRS for bakers, event directories for planners). Scoring-only
            contacts no provider.
          </p>
        </div>
        <div className="automation-toolbar__actions">
          <span
            className={`status-badge${
              capabilities?.google_places_configured ? " status-badge--success" : ""
            }`}
          >
            Google Places {capabilities?.google_places_configured ? "ready" : "not configured"}
          </span>
          <span
            className={`status-badge${
              capabilities?.instagram_connected ? " status-badge--success" : ""
            }`}
          >
            Instagram {capabilities?.instagram_connected
              ? `@${capabilities.instagram_account}`
              : "not connected"}
          </span>
          <span
            className={`status-badge${
              capabilities?.instagram_connected ? " status-badge--success" : ""
            }`}
          >
            Public registries {capabilities?.instagram_connected ? "ready" : "not connected"}
          </span>
          <button
            className="secondary-action"
            type="button"
            disabled={busy || campaigns.every((campaign) => campaign.status !== "active")}
            onClick={() => void onRunAll("scoring")}
          >
            <RefreshCw size={17} aria-hidden="true" /> Refresh scoring only
          </button>
          <button
            className="primary-action"
            type="button"
            disabled={
              busy ||
              !capabilities?.google_places_configured ||
              !campaigns.some(
                (campaign) =>
                  campaign.status === "active" &&
                  campaign.discovery_sources.includes("google_places"),
              )
            }
            onClick={() => void onRunAll("google_places")}
          >
            <RefreshCw size={17} aria-hidden="true" /> Run Google Places
          </button>
          <button
            className="primary-action"
            type="button"
            disabled={
              busy ||
              !capabilities?.instagram_connected ||
              !campaigns.some(
                (campaign) =>
                  campaign.status === "active" &&
                  campaign.discovery_sources.includes("instagram"),
              )
            }
            onClick={() => void onRunAll("instagram")}
          >
            <RefreshCw size={17} aria-hidden="true" /> Refresh Instagram profiles
          </button>
          <button
            className="primary-action"
            type="button"
            disabled={
              busy ||
              !capabilities?.instagram_connected ||
              !campaigns.some(
                (campaign) =>
                  campaign.status === "active" &&
                  campaign.discovery_sources.includes("public_registries"),
              )
            }
            onClick={() => void onRunAll("public_registries")}
          >
            <RefreshCw size={17} aria-hidden="true" /> Run public registries
          </button>
        </div>
      </div>

      {loading ? (
        <LoadingState label="Loading campaign runs" />
      ) : campaignRuns.length === 0 ? (
        <EmptyState
          title="No automation runs yet"
          description="Run one campaign or all active campaigns. No messages are generated or sent during these phases."
        />
      ) : (
        <>
          <div className="automation-run-list">
            {runPages.items.map((run) => {
              const active = ["queued", "running"].includes(run.status);
              return (
                <article className="automation-run" key={run.id}>
                  <div className="automation-run__heading">
                    <div>
                      <h3>{run.campaign_name}</h3>
                      <p>
                        {new Date(run.created_at).toLocaleString()} · {runProviderLabel(run.trigger)}
                        {" "}· phase {run.phase.replaceAll("_", " ")}
                      </p>
                    </div>
                    <span
                      className={`status-badge${
                        run.status === "completed"
                          ? " status-badge--success"
                          : run.status === "completed_with_warnings" || active
                            ? " status-badge--warning"
                            : ""
                      }`}
                    >
                      {run.status.replaceAll("_", " ")}
                    </span>
                  </div>
                  <StatGrid
                    className="automation-metrics"
                    items={[
                      { label: "Discovered", value: run.metrics.discovered ?? 0 },
                      { label: "New leads", value: run.metrics.promoted ?? 0 },
                      { label: "Scored", value: run.metrics.leads_scored ?? 0 },
                      { label: "Unchanged", value: run.metrics.scores_unchanged ?? 0 },
                      { label: "Qualified", value: run.metrics.qualified ?? 0 },
                      { label: "Shortlisted", value: run.metrics.shortlist_selected ?? 0 },
                    ]}
                  />
                  {run.warnings.map((warning) => (
                    <p className="automation-message automation-message--warning" key={warning}>
                      {warning}
                    </p>
                  ))}
                  {run.error_message ? (
                    <p className="automation-message automation-message--error">{run.error_message}</p>
                  ) : null}
                  {active ? (
                    <button
                      className="tertiary-action"
                      type="button"
                      disabled={busy || run.cancellation_requested}
                      onClick={() => void onCancelRun(run.id)}
                    >
                      <Ban size={16} aria-hidden="true" />
                      {run.cancellation_requested ? "Cancellation requested" : "Cancel run"}
                    </button>
                  ) : null}
                </article>
              );
            })}
          </div>
          <Pagination
            page={runPages.page}
            pageCount={runPages.pageCount}
            pageSize={runPages.pageSize}
            totalItems={runPages.totalItems}
            itemLabel="automation runs"
            onPageChange={runPages.setPage}
          />
        </>
      )}

      {reviewCandidates.length > 0 ? (
        <div className="candidate-review" aria-labelledby="candidate-review-heading">
          <div className="records-heading">
            <div>
              <h3 id="candidate-review-heading">Possible duplicate review</h3>
              <p>Choose whether each provider result is the suggested lead or a separate business.</p>
            </div>
          </div>
          <div className="candidate-review__list">
            {candidatePages.items.map(({ candidate, campaignName }) => (
              <article className="candidate-review__item" key={candidate.id}>
                <div>
                  <span className="eyebrow">{campaignName}</span>
                  <h3>{candidate.business_name}</h3>
                  <p>{candidate.location}</p>
                  {candidate.duplicate_confidence ? (
                    <small>{Math.round(candidate.duplicate_confidence * 100)}% name similarity</small>
                  ) : null}
                </div>
                <div className="record-actions">
                  {candidate.matched_lead_id ? (
                    <button
                      className="secondary-action"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void onCandidateDecision(candidate.id, "link", candidate.matched_lead_id ?? undefined)
                      }
                    >
                      <Link2 size={16} aria-hidden="true" /> Link suggested lead
                    </button>
                  ) : null}
                  <button
                    className="tertiary-action"
                    type="button"
                    disabled={busy}
                    onClick={() => void onCandidateDecision(candidate.id, "promote")}
                  >
                    <UserPlus size={16} aria-hidden="true" /> Create separate lead
                  </button>
                  <button
                    className="tertiary-action"
                    type="button"
                    disabled={busy}
                    onClick={() => void onCandidateDecision(candidate.id, "reject")}
                  >
                    <Ban size={16} aria-hidden="true" /> Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
          <Pagination
            page={candidatePages.page}
            pageCount={candidatePages.pageCount}
            pageSize={candidatePages.pageSize}
            totalItems={candidatePages.totalItems}
            itemLabel="duplicate candidates"
            onPageChange={candidatePages.setPage}
          />
        </div>
      ) : null}
    </section>
  );
}
