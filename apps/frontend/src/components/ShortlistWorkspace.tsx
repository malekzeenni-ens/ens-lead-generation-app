import {
  ArrowRight,
  Check,
  Clock3,
  ListChecks,
  RefreshCw,
  ShieldOff,
  X,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { formatDate, humanize, mondayIso } from "../domain";
import { usePagination } from "../pagination";
import type { Campaign, Shortlist } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { EmptyState, LoadingState, PageHeader, Pagination, SectionHeading } from "./DesignSystem";

interface ShortlistWorkspaceProps {
  campaigns: Campaign[];
  shortlists: Shortlist[];
}

export function ShortlistWorkspace({ campaigns, shortlists }: ShortlistWorkspaceProps) {
  const {
    loading,
    busy,
    generateShortlist: onGenerate,
    shortlistAction: onAction,
    manageLead: onManageLead,
  } = useWorkspaceActions();
  const activeCampaigns = campaigns.filter((campaign) => campaign.status === "active");
  const [campaignId, setCampaignId] = useState(activeCampaigns[0]?.id ?? "");
  const selectedCampaign = activeCampaigns.find((campaign) => campaign.id === campaignId);
  const latest = useMemo(
    () => shortlists.find((shortlist) => shortlist.campaign_id === campaignId) ?? shortlists[0] ?? null,
    [campaignId, shortlists],
  );
  const shortlistPages = usePagination(
    latest?.items ?? [],
    10,
    `${campaignId}|${latest?.id ?? ""}`,
  );

  useEffect(() => {
    if (!campaignId && activeCampaigns[0]) setCampaignId(activeCampaigns[0].id);
  }, [activeCampaigns, campaignId]);

  async function generate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const rawWeekStart = form.get("week-start");
    const weekStart = typeof rawWeekStart === "string" ? rawWeekStart : "";
    const size = Number(form.get("shortlist-size") ?? selectedCampaign?.weekly_shortlist_size ?? 5);
    await onGenerate(campaignId, weekStart, size);
  }

  return (
    <>
      <PageHeader
        eyebrow="Weekly focus"
        title="Weekly shortlist"
        description="Rank the strongest local opportunities using versioned scores, product fit, contact history, freshness, capacity and suppression controls."
      />

      <section className="workspace-section" aria-labelledby="shortlist-generator-heading">
        <SectionHeading
          id="shortlist-generator-heading"
          eyebrow="Recommendation engine"
          title="Generate a controlled shortlist"
          description="An existing campaign/week result is returned unchanged to preserve decisions."
          icon={ListChecks}
          count={latest?.items.filter((item) => ["recommended", "approved"].includes(item.decision)).length ?? 0}
        />
        <form className="inline-editor shortlist-generator" onSubmit={(event) => void generate(event)}>
          <label>
            Campaign
            <select
              value={campaignId}
              onChange={(event) => setCampaignId(event.target.value)}
              required
            >
              {activeCampaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
              ))}
            </select>
          </label>
          <label>Week beginning<input name="week-start" type="date" defaultValue={mondayIso()} required /></label>
          <label>
            Capacity
            <input
              key={selectedCampaign?.id}
              name="shortlist-size"
              type="number"
              min="1"
              max={selectedCampaign?.weekly_shortlist_size ?? 50}
              defaultValue={selectedCampaign?.weekly_shortlist_size ?? 5}
              required
            />
          </label>
          <button className="primary-action" type="submit" disabled={busy || !campaignId}>
            <ListChecks size={17} aria-hidden="true" /> Generate shortlist
          </button>
        </form>
        {selectedCampaign ? (
          <p className="form-hint">
            Campaign capacity: {selectedCampaign.weekly_shortlist_size} · minimum score:{" "}
            {selectedCampaign.minimum_score_threshold}/100.
          </p>
        ) : null}
      </section>

      <section className="workspace-section" aria-labelledby="weekly-results-heading">
        <SectionHeading
          id="weekly-results-heading"
          eyebrow="Human review"
          title={latest ? `${latest.campaign_name} · ${formatDate(latest.week_start)}` : "Shortlist results"}
          description="Approve, defer, dismiss or replace recommendations. No action sends a message."
          icon={ListChecks}
          count={latest?.capacity}
        />
        {loading ? (
          <LoadingState label="Loading weekly recommendations" />
        ) : !latest ? (
          <EmptyState
            title="No weekly shortlist yet"
            description="Generate the first shortlist after adding and qualifying leads."
          />
        ) : latest.items.length === 0 ? (
          <EmptyState
            title="No eligible leads"
            description="Check campaign status, score threshold, suppression and recent recommendations."
          />
        ) : (
          <>
            <div className="shortlist-grid">
            {shortlistPages.items.map((item) => (
              <article className="shortlist-card" key={item.id}>
                <div className="shortlist-rank" aria-label={`Rank ${item.rank}`}>{item.rank}</div>
                <div className="shortlist-card__body">
                  <div className="records-heading">
                    <div>
                      <h3>{item.business_name}</h3>
                      <p>{item.segment} · {item.location}</p>
                    </div>
                    <span className={`score-chip${item.score >= 70 ? " score-chip--strong" : ""}`}>
                      {item.score}/100
                    </span>
                  </div>
                  <p>{item.reason}</p>
                  {item.product_matches.length > 0 ? (
                    <details>
                      <summary>{item.product_matches.length} product match{item.product_matches.length === 1 ? "" : "es"}</summary>
                      <div className="recommendation-list">
                        {item.product_matches.map((match) => (
                          <div key={match.product_id}>
                            <strong>{match.product_name}</strong>
                            <small>{match.reason}</small>
                          </div>
                        ))}
                      </div>
                    </details>
                  ) : null}
                  <div className="shortlist-status-row">
                    <span className={`status-badge${item.decision === "approved" ? " status-badge--success" : ""}`}>
                      {humanize(item.decision)}
                    </span>
                    <button className="tertiary-action" type="button" onClick={() => onManageLead(item.lead_id)}>
                      Open lead <ArrowRight size={15} aria-hidden="true" />
                    </button>
                  </div>
                  {item.decision === "recommended" ? (
                    <div className="shortlist-actions">
                      <button type="button" className="secondary-action" disabled={busy} onClick={() => void onAction(latest.id, item.id, "approved")}>
                        <Check size={15} aria-hidden="true" /> Approve
                      </button>
                      <button type="button" className="tertiary-action" disabled={busy} onClick={() => void onAction(latest.id, item.id, "deferred")}>
                        <Clock3 size={15} aria-hidden="true" /> Defer
                      </button>
                      <button type="button" className="tertiary-action" disabled={busy} onClick={() => void onAction(latest.id, item.id, "dismissed")}>
                        <X size={15} aria-hidden="true" /> Dismiss
                      </button>
                      <button type="button" className="tertiary-action" disabled={busy} onClick={() => void onAction(latest.id, item.id, "replace")}>
                        <RefreshCw size={15} aria-hidden="true" /> Replace
                      </button>
                    </div>
                  ) : null}
                  {item.decision === "suppressed" ? (
                    <p className="suppression-note"><ShieldOff size={15} aria-hidden="true" /> Removed from the active queue by suppression.</p>
                  ) : null}
                </div>
              </article>
            ))}
            </div>
            <Pagination
              page={shortlistPages.page}
              pageCount={shortlistPages.pageCount}
              pageSize={shortlistPages.pageSize}
              totalItems={shortlistPages.totalItems}
              itemLabel="shortlist recommendations"
              onPageChange={shortlistPages.setPage}
            />
          </>
        )}
      </section>
    </>
  );
}
