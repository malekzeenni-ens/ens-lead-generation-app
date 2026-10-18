"""Campaign automation: queueing and running campaign runs, and candidate decisions.

The service is a chain, each link in its own module (R9): `base` (state and evidence
helpers) -> `promotion` -> `discovery` -> `social` -> this module. Every method keeps its
name, so callers and tests use `CampaignAutomationService` exactly as before.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    CampaignRun,
)
from app.domains.audit.service import record_audit_event
from app.domains.automation.candidate_data import (
    DEFAULT_METRICS,
    _run_to_read,
)
from app.domains.automation.schemas import (
    CampaignRunProvider,
    CampaignRunRead,
    CampaignRunStatus,
    CandidateDecision,
    CandidateDecisionAction,
    CandidateStatus,
    DiscoveryCandidateRead,
)
from app.domains.automation.social import AutomationSocial

logger = logging.getLogger(__name__)


class CampaignAutomationService(AutomationSocial):
    def queue(
        self,
        session: Session,
        campaign_id: str,
        *,
        batch_id: str | None = None,
        trigger: str | None = None,
        week_start: date | None = None,
        requested_provider: CampaignRunProvider = CampaignRunProvider.SCORING,
        correlation_id: str,
    ) -> str:
        campaign = self.campaign_repository.get(session, campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        if campaign.status != "active":
            raise DomainError(
                "CAMPAIGN_NOT_ACTIVE",
                "Only active campaigns can be run.",
                status_code=409,
            )
        if (
            requested_provider is not CampaignRunProvider.SCORING
            and requested_provider.value not in campaign.discovery_sources
        ):
            raise DomainError(
                "CAMPAIGN_PROVIDER_NOT_SELECTED",
                f"{requested_provider.value.replace('_', ' ').title()} is not selected for "
                "this campaign.",
                status_code=409,
            )
        active = session.scalar(
            select(CampaignRun).where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status.in_(("queued", "running")),
            )
        )
        if active is not None:
            raise DomainError(
                "CAMPAIGN_RUN_ACTIVE",
                "This campaign already has an active run.",
                status_code=409,
                details={"campaign_run_id": active.id},
            )
        run = CampaignRun(
            batch_id=batch_id or str(uuid4()),
            campaign_id=campaign_id,
            trigger=trigger or f"manual_{requested_provider.value}",
            week_start=week_start,
            status=CampaignRunStatus.QUEUED.value,
            phase="queued",
            metrics=dict(DEFAULT_METRICS),
        )
        session.add(run)
        session.flush()
        record_audit_event(
            session,
            action="campaign_run.queued",
            entity_type="campaign_run",
            entity_id=run.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": campaign_id,
                "batch_id": run.batch_id,
                "provider": requested_provider.value,
            },
        )
        session.commit()
        return run.id

    def list_runs(
        self, session: Session, *, campaign_id: str | None = None
    ) -> list[CampaignRunRead]:
        return [
            _run_to_read(run) for run in self.repository.list_runs(session, campaign_id=campaign_id)
        ]

    def request_cancellation(
        self, session: Session, run_id: str, correlation_id: str
    ) -> CampaignRunRead:
        run = self.repository.get_run(session, run_id)
        if run is None:
            raise DomainError("CAMPAIGN_RUN_NOT_FOUND", "Campaign run not found.", status_code=404)
        if run.status not in {"queued", "running"}:
            raise DomainError(
                "CAMPAIGN_RUN_FINISHED",
                "Only an active campaign run can be cancelled.",
                status_code=409,
            )
        run.cancellation_requested = True
        record_audit_event(
            session,
            action="campaign_run.cancellation_requested",
            entity_type="campaign_run",
            entity_id=run.id,
            correlation_id=correlation_id,
            summary={"campaign_id": run.campaign_id},
        )
        session.commit()
        session.expire_all()
        stored = self.repository.get_run(session, run_id)
        if stored is None:
            raise RuntimeError("Campaign run could not be reloaded")
        return _run_to_read(stored)

    def execute(self, session: Session, run_id: str, correlation_id: str) -> None:
        run = self.repository.get_run(session, run_id)
        if run is None:
            return
        if run.status in {
            CampaignRunStatus.COMPLETED.value,
            CampaignRunStatus.COMPLETED_WITH_WARNINGS.value,
            CampaignRunStatus.CANCELLED.value,
        }:
            return
        run.status = CampaignRunStatus.RUNNING.value
        run.phase = "discovery"
        run.started_at = run.started_at or datetime.now(UTC)
        run.error_code = None
        run.error_message = None
        session.commit()
        try:
            campaign = self.campaign_repository.get(session, run.campaign_id)
            if campaign is None or campaign.status != "active":
                raise DomainError(
                    "CAMPAIGN_NOT_ACTIVE",
                    "The campaign is no longer active.",
                    status_code=409,
                )
            self._cancel_if_requested(session, run)
            self._discover(session, run, campaign)
            self._cancel_if_requested(session, run)
            run.phase = "qualification"
            session.commit()
            qualification = self.qualification.refresh_campaign_scores(
                session,
                campaign,
                run.id,
                correlation_id,
            )
            metrics = dict(DEFAULT_METRICS) | run.metrics
            metrics.update(
                {
                    "leads_scored": qualification.scored,
                    "scores_unchanged": qualification.unchanged,
                    "qualified": qualification.qualified,
                    "skipped": qualification.skipped,
                }
            )
            run.metrics = metrics
            run.phase = "shortlist"
            session.commit()
            self._cancel_if_requested(session, run)
            prepared = self.qualification.prepare_shortlist_from_scores(
                session,
                campaign,
                qualification.score_runs,
                correlation_id,
            )
            metrics = dict(DEFAULT_METRICS) | run.metrics
            metrics["shortlist_selected"] = len(prepared.shortlist.items)
            metrics["shortlist_created"] = int(prepared.created)
            run.metrics = metrics
            run.phase = "completed"
            run.status = (
                CampaignRunStatus.COMPLETED_WITH_WARNINGS.value
                if run.warnings
                else CampaignRunStatus.COMPLETED.value
            )
            run.completed_at = datetime.now(UTC)
            record_audit_event(
                session,
                action="campaign_run.completed",
                entity_type="campaign_run",
                entity_id=run.id,
                correlation_id=correlation_id,
                summary={
                    "campaign_id": run.campaign_id,
                    "status": run.status,
                    "metrics": run.metrics,
                },
            )
            session.commit()
        except InterruptedError:
            return
        except DomainError as exc:
            logger.warning(
                "Campaign run failed", extra={"campaign_run_id": run_id, "error_code": exc.code}
            )
            self._fail_run(session, run_id, exc.code, exc.message)
        except Exception:
            logger.exception("Campaign run failed", extra={"campaign_run_id": run_id})
            self._fail_run(
                session,
                run_id,
                "CAMPAIGN_RUN_FAILED",
                "The campaign run failed safely; existing data was retained.",
            )

    def _fail_run(self, session: Session, run_id: str, code: str, message: str) -> None:
        """Record a failed run without keeping its unfinished work.

        Work up to the last commit stays: each provider batch, with its evidence, and each phase
        transition is committed on its own. Anything after that is rolled back, so a failure part
        way through a batch cannot leave a lead without its campaign link or evidence. A provider
        attempt rolled back to `running` is closed as failed.
        """
        session.rollback()
        run = self.repository.get_run(session, run_id)
        if run is None:
            return
        now = datetime.now(UTC)
        for attempt in run.attempts:
            if attempt.status == "running":
                attempt.status = "failed"
                attempt.error_code = code
                attempt.error_message = message
                attempt.completed_at = now
        run.status = CampaignRunStatus.FAILED.value
        run.phase = "failed"
        run.error_code = code
        run.error_message = message
        run.completed_at = now
        session.commit()

    def decide_candidate(
        self,
        session: Session,
        candidate_id: str,
        data: CandidateDecision,
        correlation_id: str,
    ) -> DiscoveryCandidateRead:
        candidate = self.repository.get_candidate(session, candidate_id)
        if candidate is None:
            raise DomainError(
                "DISCOVERY_CANDIDATE_NOT_FOUND", "Discovery candidate not found.", status_code=404
            )
        if candidate.status not in {"review_required", "discovered"}:
            raise DomainError(
                "DISCOVERY_CANDIDATE_DECIDED",
                "This discovery candidate already has a final decision.",
                status_code=409,
            )
        previous_status = candidate.status
        if data.action is CandidateDecisionAction.REJECT:
            candidate.status = CandidateStatus.REJECTED.value
            candidate.rejection_reason = data.reason or "Rejected during duplicate review."
        elif data.action is CandidateDecisionAction.LINK:
            if data.lead_id is None:
                raise DomainError(
                    "LEAD_ID_REQUIRED",
                    "A lead ID is required when linking a candidate.",
                    status_code=422,
                )
            lead = self.lead_repository.get(session, data.lead_id)
            if lead is None:
                raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
            self._link_existing(session, candidate, lead)
        else:
            candidate.matched_lead_id = None
            candidate.duplicate_confidence = None
            self._promote_candidate(session, candidate, force=True)
        metrics = dict(DEFAULT_METRICS) | candidate.run.metrics
        if previous_status in metrics:
            metrics[previous_status] = max(0, metrics[previous_status] - 1)
        if candidate.status in metrics:
            metrics[candidate.status] += 1
        candidate.run.metrics = metrics
        if candidate.matched_lead_id and data.action is not CandidateDecisionAction.REJECT:
            campaign = self.campaign_repository.get(session, candidate.campaign_id)
            if campaign is not None:
                self._refresh_qualification(session, candidate.run, campaign, correlation_id)
        record_audit_event(
            session,
            action=f"discovery_candidate.{data.action.value}",
            entity_type="discovery_candidate",
            entity_id=candidate.id,
            correlation_id=correlation_id,
            summary={
                "campaign_id": candidate.campaign_id,
                "matched_lead_id": candidate.matched_lead_id,
                "reason_provided": bool(data.reason),
            },
        )
        session.commit()
        session.refresh(candidate)
        return DiscoveryCandidateRead.model_validate(candidate)
