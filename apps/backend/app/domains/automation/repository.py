from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CampaignRun, DiscoveryCandidate, Lead, LeadCampaign, ProviderAttempt

_RUN_OPTIONS = (
    selectinload(CampaignRun.campaign),
    selectinload(CampaignRun.candidates),
    selectinload(CampaignRun.attempts),
)


class AutomationRepository:
    def get_run(self, session: Session, run_id: str) -> CampaignRun | None:
        return session.scalar(
            select(CampaignRun).where(CampaignRun.id == run_id).options(*_RUN_OPTIONS)
        )

    def list_runs(
        self, session: Session, *, campaign_id: str | None = None, limit: int = 50
    ) -> list[CampaignRun]:
        statement = select(CampaignRun).options(*_RUN_OPTIONS)
        if campaign_id:
            statement = statement.where(CampaignRun.campaign_id == campaign_id)
        return list(session.scalars(statement.order_by(CampaignRun.created_at.desc()).limit(limit)))

    def interrupt_running_attempts(self, session: Session) -> list[str]:
        """Close provider attempts a previous process left running. Startup only."""
        attempts = list(
            session.scalars(select(ProviderAttempt).where(ProviderAttempt.status == "running"))
        )
        now = datetime.now(UTC)
        for attempt in attempts:
            attempt.status = "interrupted"
            attempt.error_code = "PROCESS_INTERRUPTED"
            attempt.error_message = "The app closed before this provider call finished."
            attempt.completed_at = now
        return [attempt.id for attempt in attempts]

    def incomplete_runs(self, session: Session) -> list[CampaignRun]:
        return list(
            session.scalars(
                select(CampaignRun).where(CampaignRun.status.in_(("queued", "running")))
            )
        )

    def get_candidate(self, session: Session, candidate_id: str) -> DiscoveryCandidate | None:
        return session.get(DiscoveryCandidate, candidate_id)

    def previous_provider_match(
        self, session: Session, provider: str, provider_record_id: str
    ) -> DiscoveryCandidate | None:
        return session.scalar(
            select(DiscoveryCandidate)
            .where(
                DiscoveryCandidate.provider == provider,
                DiscoveryCandidate.provider_record_id == provider_record_id,
                DiscoveryCandidate.matched_lead_id.is_not(None),
                DiscoveryCandidate.status.in_(("promoted", "linked_existing")),
            )
            .order_by(DiscoveryCandidate.created_at.desc())
            .limit(1)
        )

    def candidate_leads(self, session: Session) -> list[Lead]:
        return list(
            session.scalars(
                select(Lead)
                .options(selectinload(Lead.social_identities))
                .order_by(Lead.created_at.desc())
            )
        )

    def is_linked(self, session: Session, lead_id: str, campaign_id: str) -> bool:
        return (
            session.get(
                LeadCampaign,
                {"lead_id": lead_id, "campaign_id": campaign_id},
            )
            is not None
        )

    def add_attempt(self, session: Session, attempt: ProviderAttempt) -> None:
        session.add(attempt)
