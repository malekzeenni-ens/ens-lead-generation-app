from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from uuid import uuid4

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import CampaignRun
from app.db.session import Database
from app.domains.automation.providers import MetaInstagramProvider
from app.domains.automation.schemas import CampaignRunProvider
from app.domains.automation.service import CampaignAutomationService


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

    def resume_incomplete(self) -> None:
        with self.database.session_factory() as session:
            service = CampaignAutomationService(self.settings)
            run_ids = [run.id for run in service.repository.incomplete_runs(session)]
        for run_id in run_ids:
            self.submit(run_id, str(uuid4()))

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
