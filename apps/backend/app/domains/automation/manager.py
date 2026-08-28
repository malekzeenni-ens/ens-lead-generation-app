from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from uuid import uuid4

from sqlalchemy import select

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import CampaignRun
from app.db.session import Database
from app.domains.automation.providers import MetaInstagramProvider
from app.domains.automation.schemas import CampaignRunProvider
from app.domains.automation.service import CampaignAutomationService
from app.domains.automation.weekly import WeeklyOutreachService, current_week_start

logger = logging.getLogger(__name__)


class CampaignRunManager:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        instagram_provider: MetaInstagramProvider | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.instagram_provider = instagram_provider
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="campaign-run")
        self._futures: dict[str, Future[None]] = {}
        self._lock = Lock()

    def _execute(self, run_id: str, correlation_id: str) -> None:
        try:
            with self.database.session_factory() as session:
                CampaignAutomationService(
                    self.settings, instagram_provider=self.instagram_provider
                ).execute(session, run_id, correlation_id)
        finally:
            with self._lock:
                self._futures.pop(run_id, None)

    def _execute_weekly(self, run_ids: list[str], correlation_id: str) -> None:
        try:
            for run_id in run_ids:
                with self.database.session_factory() as session:
                    run = session.get(CampaignRun, run_id)
                    if run is None or run.status in {"failed", "cancelled"}:
                        continue
                    if run.phase not in {"waiting_for_campaigns", "outreach"}:
                        CampaignAutomationService(
                            self.settings, instagram_provider=self.instagram_provider
                        ).execute(session, run_id, correlation_id)
                        run = session.get(CampaignRun, run_id)
                    if run is not None and run.status in {
                        "completed",
                        "completed_with_warnings",
                    }:
                        run.status = "running"
                        run.phase = "waiting_for_campaigns"
                        run.completed_at = None
                        session.commit()
            with self.database.session_factory() as session:
                WeeklyOutreachService().prepare(session, run_ids, correlation_id)
        except Exception:
            logger.exception("Weekly outreach preparation failed")
            with self.database.session_factory() as session:
                runs = list(session.scalars(select(CampaignRun).where(CampaignRun.id.in_(run_ids))))
                for run in runs:
                    if run.status == "running":
                        run.status = "failed"
                        run.phase = "failed"
                        run.error_code = "WEEKLY_OUTREACH_FAILED"
                        run.error_message = (
                            "Weekly outreach failed safely; existing leads and drafts were "
                            "retained."
                        )
                session.commit()
        finally:
            with self._lock:
                for run_id in run_ids:
                    self._futures.pop(run_id, None)

    def submit(self, run_id: str, correlation_id: str) -> None:
        if self.settings.campaign_run_inline:
            self._execute(run_id, correlation_id)
            return
        with self._lock:
            if run_id in self._futures:
                return
            self._futures[run_id] = self._executor.submit(self._execute, run_id, correlation_id)

    def queue_one(
        self,
        campaign_id: str,
        provider: CampaignRunProvider,
        correlation_id: str,
    ) -> str:
        with self.database.session_factory() as session:
            run_id = CampaignAutomationService(self.settings).queue(
                session,
                campaign_id,
                requested_provider=provider,
                correlation_id=correlation_id,
            )
        self.submit(run_id, correlation_id)
        return run_id

    def queue_all(self, provider: CampaignRunProvider, correlation_id: str) -> list[str]:
        with self.database.session_factory() as session:
            service = CampaignAutomationService(self.settings)
            campaigns = service.campaign_repository.list(session, status="active")
            running_campaign_ids = set(
                session.scalars(
                    select(CampaignRun.campaign_id).where(
                        CampaignRun.status.in_(("queued", "running"))
                    )
                )
            )
            batch_id = str(uuid4())
            run_ids = [
                service.queue(
                    session,
                    campaign.id,
                    batch_id=batch_id,
                    trigger=f"manual_all_{provider.value}",
                    requested_provider=provider,
                    correlation_id=correlation_id,
                )
                for campaign in campaigns
                if campaign.id not in running_campaign_ids
                and (
                    provider is CampaignRunProvider.SCORING
                    or provider.value in campaign.discovery_sources
                )
            ]
        for run_id in run_ids:
            self.submit(run_id, correlation_id)
        return run_ids

    def queue_weekly_due(self, correlation_id: str) -> list[str]:
        week_start = current_week_start()
        new_run_ids: list[str] = []
        with self.database.session_factory() as session:
            service = CampaignAutomationService(self.settings)
            campaigns = [
                campaign
                for campaign in service.campaign_repository.list(session, status="active")
                if campaign.weekly_outreach_enabled
            ]
            existing = {
                run.campaign_id: run
                for run in session.scalars(
                    select(CampaignRun).where(CampaignRun.week_start == week_start)
                )
            }
            batch_id = str(uuid4())
            for campaign in campaigns:
                if campaign.id in existing:
                    continue
                provider = CampaignRunProvider(campaign.weekly_outreach_provider)
                try:
                    run_id = service.queue(
                        session,
                        campaign.id,
                        batch_id=batch_id,
                        trigger=f"weekly_{provider.value}",
                        week_start=week_start,
                        requested_provider=provider,
                        correlation_id=correlation_id,
                    )
                except DomainError as exc:
                    if exc.code == "CAMPAIGN_RUN_ACTIVE":
                        continue
                    raise
                new_run_ids.append(run_id)
            current_ids = [
                run.id
                for run in session.scalars(
                    select(CampaignRun).where(CampaignRun.week_start == week_start)
                )
            ]

        if new_run_ids:
            self.submit_weekly(new_run_ids, correlation_id)
        return current_ids

    def submit_weekly(self, run_ids: list[str], correlation_id: str) -> None:
        if not run_ids:
            return
        if self.settings.campaign_run_inline:
            self._execute_weekly(run_ids, correlation_id)
            return
        with self._lock:
            pending = [run_id for run_id in run_ids if run_id not in self._futures]
            if not pending:
                return
            future = self._executor.submit(self._execute_weekly, pending, correlation_id)
            for run_id in pending:
                self._futures[run_id] = future

    def retry_weekly(self, run_id: str, correlation_id: str) -> None:
        with self.database.session_factory() as session:
            run = session.get(CampaignRun, run_id)
            if run is None or run.week_start is None:
                raise DomainError(
                    "WEEKLY_RUN_NOT_FOUND", "Weekly campaign run not found.", status_code=404
                )
            if run.status != "failed":
                raise DomainError(
                    "WEEKLY_RUN_NOT_FAILED",
                    "Only a failed weekly run can be retried.",
                    status_code=409,
                )
            run.status = "queued"
            run.phase = "queued"
            run.error_code = None
            run.error_message = None
            run.cancellation_requested = False
            run.completed_at = None
            session.commit()
        self.submit_weekly([run_id], correlation_id)

    def resume_incomplete(self) -> None:
        with self.database.session_factory() as session:
            service = CampaignAutomationService(self.settings)
            runs = service.repository.incomplete_runs(session)
            weekly_groups: dict[str, list[str]] = {}
            manual_run_ids: list[str] = []
            for run in runs:
                if run.week_start is None:
                    manual_run_ids.append(run.id)
                else:
                    weekly_groups.setdefault(run.batch_id, []).append(run.id)
        for run_id in manual_run_ids:
            self.submit(run_id, str(uuid4()))
        for run_ids in weekly_groups.values():
            self.submit_weekly(run_ids, str(uuid4()))

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
