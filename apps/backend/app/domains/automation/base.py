"""Shared state and evidence helpers for campaign automation.

Part of the CampaignAutomationService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import (
    Campaign,
    CampaignRun,
    SourceObservation,
    SourceSystem,
)
from app.domains.automation.candidate_data import (
    DEFAULT_METRICS,
    _run_to_read,
)
from app.domains.automation.enrichment import SafeWebsiteEnricher
from app.domains.automation.providers import (
    GooglePlacesProvider,
    MetaInstagramProvider,
)
from app.domains.automation.repository import AutomationRepository
from app.domains.automation.schemas import (
    CampaignRunRead,
    CampaignRunStatus,
)
from app.domains.campaigns.repository import CampaignRepository
from app.domains.leads.repository import LeadRepository
from app.domains.qualification.service import QualificationService

logger = logging.getLogger(__name__)


class AutomationBase:
    def __init__(
        self,
        settings: Settings,
        repository: AutomationRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
        lead_repository: LeadRepository | None = None,
        qualification: QualificationService | None = None,
        provider: GooglePlacesProvider | None = None,
        instagram_provider: MetaInstagramProvider | None = None,
        enricher: SafeWebsiteEnricher | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository or AutomationRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()
        self.lead_repository = lead_repository or LeadRepository()
        self.qualification = qualification or QualificationService()
        self.provider = provider or GooglePlacesProvider(settings)
        self.instagram_provider = instagram_provider
        self.enricher = enricher or SafeWebsiteEnricher(settings)

    def get_run(self, session: Session, run_id: str) -> CampaignRunRead:
        run = self.repository.get_run(session, run_id)
        if run is None:
            raise DomainError("CAMPAIGN_RUN_NOT_FOUND", "Campaign run not found.", status_code=404)
        return _run_to_read(run)

    @staticmethod
    def _cancel_if_requested(session: Session, run: CampaignRun) -> None:
        session.refresh(run, attribute_names=["cancellation_requested"])
        if run.cancellation_requested:
            run.status = CampaignRunStatus.CANCELLED.value
            run.phase = "cancelled"
            run.completed_at = datetime.now(UTC)
            session.commit()
            raise InterruptedError("Campaign run cancelled")

    @staticmethod
    def _source_system(session: Session, name: str, source_type: str) -> SourceSystem:
        source = session.scalar(select(SourceSystem).where(SourceSystem.name == name))
        if source is None:
            source = SourceSystem(name=name, source_type=source_type)
            session.add(source)
            session.flush()
        return source

    @staticmethod
    def _add_observation(
        session: Session,
        *,
        lead_id: str,
        source: SourceSystem,
        field_name: str,
        value: str | None,
        source_url: str | None,
        collection_method: str,
    ) -> None:
        if not value:
            return
        existing = session.scalar(
            select(SourceObservation).where(
                SourceObservation.lead_id == lead_id,
                SourceObservation.source_system_id == source.id,
                SourceObservation.field_name == field_name,
                SourceObservation.observed_value == value,
                SourceObservation.source_url == source_url,
            )
        )
        if existing is not None:
            return
        session.add(
            SourceObservation(
                lead_id=lead_id,
                source_system_id=source.id,
                field_name=field_name,
                observed_value=value,
                classification="provider_observed",
                source_url=source_url,
                collection_method=collection_method,
                collected_at=datetime.now(UTC),
            )
        )

    def _refresh_qualification(
        self,
        session: Session,
        run: CampaignRun,
        campaign: Campaign,
        correlation_id: str,
    ) -> None:
        qualification = self.qualification.refresh_campaign_scores(
            session, campaign, run.id, correlation_id
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
        prepared = self.qualification.prepare_shortlist_from_scores(
            session, campaign, qualification.score_runs, correlation_id
        )
        metrics["shortlist_selected"] = len(prepared.shortlist.items)
        metrics["shortlist_created"] = int(prepared.created)
        run.metrics = metrics
