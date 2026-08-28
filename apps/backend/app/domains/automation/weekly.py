from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CampaignRun, Lead, ScoreRun, Shortlist, ShortlistItem, Template
from app.domains.audit.service import record_audit_event
from app.domains.outreach.schemas import OutreachBatchCreate
from app.domains.outreach.service import OutreachService
from app.domains.system.service import SystemService

logger = logging.getLogger(__name__)


def current_week_start(now: datetime | None = None) -> date:
    # This is a local-first desktop app, so its weekly boundary follows the
    # timezone configured on the user's computer (including its DST rules).
    local_now = now.astimezone() if now else datetime.now().astimezone()
    return local_now.date() - timedelta(days=local_now.weekday())


@dataclass(frozen=True)
class _Candidate:
    run_id: str
    campaign_name: str
    lead: Lead
    score: int
    rank: int


class WeeklyOutreachService:
    def __init__(self, outreach: OutreachService | None = None) -> None:
        self.outreach = outreach or OutreachService()

    @staticmethod
    def _shortlist(session: Session, run: CampaignRun) -> Shortlist | None:
        if run.week_start is None:
            return None
        return session.scalar(
            select(Shortlist)
            .where(
                Shortlist.campaign_id == run.campaign_id,
                Shortlist.week_start == run.week_start,
            )
            .options(
                selectinload(Shortlist.items).selectinload(ShortlistItem.lead),
                selectinload(Shortlist.campaign),
            )
        )

    @staticmethod
    def _score(session: Session, item: ShortlistItem) -> int:
        score = session.get(ScoreRun, item.score_run_id) if item.score_run_id else None
        return score.final_score if score else (item.lead.current_score or 0)

    @staticmethod
    def _append_warning(run: CampaignRun, message: str) -> None:
        if message not in run.warnings:
            run.warnings = [*run.warnings, message]

    def prepare(self, session: Session, run_ids: list[str], correlation_id: str) -> None:
        runs = list(
            session.scalars(
                select(CampaignRun)
                .where(CampaignRun.id.in_(run_ids))
                .options(selectinload(CampaignRun.campaign))
            )
        )
        eligible_runs = [
            run
            for run in runs
            if run.week_start is not None
            and run.status == "running"
            and run.phase in {"waiting_for_campaigns", "outreach"}
        ]
        if not eligible_runs:
            return

        candidates: list[_Candidate] = []
        templates: dict[str, Template] = {}
        for run in eligible_runs:
            run.phase = "outreach"
            template = (
                session.get(Template, run.campaign.weekly_outreach_template_id)
                if run.campaign.weekly_outreach_template_id
                else None
            )
            if template is None:
                metrics = dict(run.metrics)
                metrics["attention_required"] = metrics.get("attention_required", 0) + 1
                run.metrics = metrics
                self._append_warning(run, "Choose a valid weekly email template for this campaign.")
                continue
            templates[run.id] = template
            shortlist = self._shortlist(session, run)
            if shortlist is None:
                metrics = dict(run.metrics)
                metrics["attention_required"] = metrics.get("attention_required", 0) + 1
                run.metrics = metrics
                self._append_warning(
                    run, "The weekly shortlist was not available for draft preparation."
                )
                continue
            for item in shortlist.items:
                if item.decision not in {"recommended", "approved"}:
                    continue
                candidates.append(
                    _Candidate(
                        run_id=run.id,
                        campaign_name=run.campaign.name,
                        lead=item.lead,
                        score=self._score(session, item),
                        rank=item.rank,
                    )
                )

        winners: dict[str, _Candidate] = {}
        for candidate in candidates:
            current = winners.get(candidate.lead.id)
            if current is None or (
                candidate.score,
                -candidate.rank,
                candidate.campaign_name.casefold(),
            ) > (
                current.score,
                -current.rank,
                current.campaign_name.casefold(),
            ):
                winners[candidate.lead.id] = candidate

        by_run = {run.id: run for run in eligible_runs}
        for candidate in candidates:
            if winners[candidate.lead.id] is candidate:
                continue
            run = by_run[candidate.run_id]
            metrics = dict(run.metrics)
            metrics["cross_campaign_duplicates"] = metrics.get("cross_campaign_duplicates", 0) + 1
            metrics["outreach_skipped"] = metrics.get("outreach_skipped", 0) + 1
            run.metrics = metrics

        ordered = sorted(
            winners.values(),
            key=lambda item: (-item.score, item.rank, item.campaign_name.casefold()),
        )
        global_limit = SystemService().get_settings(session).weekly_outreach_global_limit
        selected = ordered[:global_limit]
        for candidate in ordered[global_limit:]:
            run = by_run[candidate.run_id]
            metrics = dict(run.metrics)
            metrics["weekly_limit_skipped"] = metrics.get("weekly_limit_skipped", 0) + 1
            metrics["outreach_skipped"] = metrics.get("outreach_skipped", 0) + 1
            run.metrics = metrics

        ready_by_run: dict[str, list[str]] = {run.id: [] for run in eligible_runs}
        for candidate in selected:
            run = by_run[candidate.run_id]
            template = templates.get(run.id)
            if template is None:
                continue
            eligibility = self.outreach._eligibility(session, candidate.lead)
            context_blockers = self.outreach.template_blockers(session, candidate.lead, template)
            reasons = [*eligibility.blockers, *eligibility.warnings, *context_blockers]
            if reasons:
                metrics = dict(run.metrics)
                metrics["attention_required"] = metrics.get("attention_required", 0) + 1
                metrics["outreach_skipped"] = metrics.get("outreach_skipped", 0) + 1
                if context_blockers:
                    metrics["missing_context"] = metrics.get("missing_context", 0) + 1
                run.metrics = metrics
                self._append_warning(
                    run,
                    f"{candidate.lead.business_name}: {'; '.join(reasons)}",
                )
                continue
            ready_by_run[run.id].append(candidate.lead.id)

        session.commit()
        failed_run_ids: set[str] = set()
        for run_id, lead_ids in ready_by_run.items():
            if not lead_ids:
                continue
            stored_run = session.get(CampaignRun, run_id)
            if stored_run is None or run_id not in templates:
                continue
            try:
                batch = self.outreach.create_batch(
                    session,
                    OutreachBatchCreate(
                        lead_ids=lead_ids,
                        template_id=templates[run_id].id,
                        campaign_id=stored_run.campaign_id,
                    ),
                    correlation_id,
                )
            except Exception:
                logger.exception(
                    "Weekly draft preparation failed for one campaign",
                    extra={"campaign_run_id": run_id},
                )
                session.rollback()
                failed_run = session.get(CampaignRun, run_id)
                if failed_run is not None:
                    failed_run.status = "failed"
                    failed_run.phase = "failed"
                    failed_run.error_code = "WEEKLY_DRAFT_PREPARATION_FAILED"
                    failed_run.error_message = (
                        "Draft preparation failed safely for this campaign. Other campaigns "
                        "continued. Retry this campaign from the dashboard."
                    )
                    failed_run.completed_at = datetime.now(UTC)
                    session.commit()
                failed_run_ids.add(run_id)
                continue
            stored_run = session.get(CampaignRun, run_id)
            if stored_run is None:
                continue
            metrics = dict(stored_run.metrics)
            metrics["drafts_created"] = len(batch.drafts)
            stored_run.metrics = metrics
            stored_run.outreach_batch_id = batch.id
            session.commit()

        for run_id in ready_by_run:
            if run_id in failed_run_ids:
                continue
            stored_run = session.get(CampaignRun, run_id)
            if stored_run is None:
                continue
            stored_run.phase = "completed"
            stored_run.status = "completed_with_warnings" if stored_run.warnings else "completed"
            stored_run.completed_at = datetime.now(UTC)
            record_audit_event(
                session,
                action="weekly_outreach.completed",
                entity_type="campaign_run",
                entity_id=stored_run.id,
                correlation_id=correlation_id,
                summary={
                    "campaign_id": stored_run.campaign_id,
                    "week_start": (
                        stored_run.week_start.isoformat() if stored_run.week_start else None
                    ),
                    "outreach_batch_id": stored_run.outreach_batch_id,
                    "metrics": stored_run.metrics,
                },
            )
        session.commit()
