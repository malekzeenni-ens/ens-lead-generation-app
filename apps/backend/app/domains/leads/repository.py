from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Communication,
    FollowUp,
    Lead,
    LeadCampaign,
    LeadNote,
    LeadSocialIdentity,
    SourceObservation,
    SuppressionRecord,
)

_LEAD_OPTIONS = (
    selectinload(Lead.campaigns),
    selectinload(Lead.observations).selectinload(SourceObservation.source_system),
    selectinload(Lead.social_identities),
    selectinload(Lead.stage_events),
    selectinload(Lead.notes),
    selectinload(Lead.follow_ups),
    selectinload(Lead.communications),
    selectinload(Lead.suppression_records),
)


class LeadRepository:
    def get(self, session: Session, lead_id: str) -> Lead | None:
        return session.scalar(select(Lead).where(Lead.id == lead_id).options(*_LEAD_OPTIONS))

    def list(
        self,
        session: Session,
        *,
        query: str | None = None,
        stage: str | None = None,
        suppressed: bool | None = None,
        campaign_id: str | None = None,
    ) -> list[Lead]:
        statement = select(Lead).options(*_LEAD_OPTIONS)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    Lead.business_name.ilike(pattern),
                    Lead.segment.ilike(pattern),
                    Lead.location.ilike(pattern),
                    Lead.phone_number.ilike(pattern),
                    Lead.public_email.ilike(pattern),
                )
            )
        if stage:
            statement = statement.where(Lead.pipeline_stage == stage)
        if suppressed is not None:
            statement = statement.where(Lead.suppressed.is_(suppressed))
        if campaign_id:
            statement = statement.where(Lead.campaigns.any(LeadCampaign.campaign_id == campaign_id))
        statement = statement.order_by(Lead.created_at.desc())
        return list(session.scalars(statement))

    def find_exact(self, session: Session, normalized_name: str, location: str) -> Lead | None:
        statement = select(Lead).where(
            Lead.normalized_name == normalized_name,
            Lead.location.collate("NOCASE") == location,
        )
        return session.scalar(statement)

    def find_social_identity(
        self, session: Session, platform: str, normalized_handle: str
    ) -> LeadSocialIdentity | None:
        return session.scalar(
            select(LeadSocialIdentity).where(
                LeadSocialIdentity.platform == platform,
                LeadSocialIdentity.normalized_handle == normalized_handle,
            )
        )

    def add(self, session: Session, lead: Lead) -> None:
        session.add(lead)

    def link_campaign(self, session: Session, lead_id: str, campaign_id: str) -> None:
        session.add(LeadCampaign(lead_id=lead_id, campaign_id=campaign_id))

    def active_suppression_by_hash(
        self, session: Session, identifier_hash: str
    ) -> SuppressionRecord | None:
        return session.scalar(
            select(SuppressionRecord).where(
                SuppressionRecord.identifier_hash == identifier_hash,
                SuppressionRecord.active.is_(True),
            )
        )

    def get_follow_up(self, session: Session, lead_id: str, follow_up_id: str) -> FollowUp | None:
        return session.scalar(
            select(FollowUp).where(FollowUp.id == follow_up_id, FollowUp.lead_id == lead_id)
        )

    def add_note(self, session: Session, note: LeadNote) -> None:
        session.add(note)

    def add_follow_up(self, session: Session, follow_up: FollowUp) -> None:
        session.add(follow_up)

    def add_communication(self, session: Session, communication: Communication) -> None:
        session.add(communication)
