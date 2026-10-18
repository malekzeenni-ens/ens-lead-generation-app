import builtins
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Communication,
    FollowUp,
    Lead,
    LeadCampaign,
    LeadNote,
    LeadSocialIdentity,
    ScoreRun,
    SourceObservation,
    SourceSystem,
)

_LEAD_OPTIONS = (
    selectinload(Lead.campaigns).selectinload(LeadCampaign.campaign),
    selectinload(Lead.observations).selectinload(SourceObservation.source_system),
    selectinload(Lead.social_identities),
    selectinload(Lead.stage_events),
    selectinload(Lead.notes),
    selectinload(Lead.follow_ups),
    selectinload(Lead.communications),
    selectinload(Lead.suppression_records),
    selectinload(Lead.score_runs).selectinload(ScoreRun.campaign),
)


@dataclass(frozen=True)
class LeadFilters:
    query: str | None = None
    stage: str | None = None
    suppressed: bool | None = None
    campaign_id: str | None = None
    # As the register shows it: lower-case, never "website"; "unknown" means no other source.
    source_type: str | None = None
    needs_review: bool | None = None


def _normalised_source_type() -> ColumnElement[str]:
    return func.lower(func.trim(SourceSystem.source_type))


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
                    Lead.contact_first_name.ilike(pattern),
                    Lead.contact_last_name.ilike(pattern),
                    Lead.contact_email.ilike(pattern),
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

    @staticmethod
    def _page_conditions(filters: LeadFilters) -> builtins.list[ColumnElement[bool]]:
        conditions: builtins.list[ColumnElement[bool]] = []
        if filters.query:
            pattern = f"%{filters.query}%"
            conditions.append(
                or_(
                    Lead.business_name.ilike(pattern),
                    Lead.segment.ilike(pattern),
                    Lead.location.ilike(pattern),
                    Lead.phone_number.ilike(pattern),
                    Lead.public_email.ilike(pattern),
                    Lead.contact_first_name.ilike(pattern),
                    Lead.contact_last_name.ilike(pattern),
                    Lead.contact_email.ilike(pattern),
                )
            )
        if filters.stage:
            conditions.append(Lead.pipeline_stage == filters.stage)
        if filters.suppressed is not None:
            conditions.append(Lead.suppressed.is_(filters.suppressed))
        if filters.campaign_id:
            conditions.append(Lead.campaigns.any(LeadCampaign.campaign_id == filters.campaign_id))
        if filters.needs_review is not None:
            unknown = Lead.contact_classification == "unknown"
            conditions.append(unknown if filters.needs_review else ~unknown)
        if filters.source_type:
            named_sources = (
                select(SourceObservation.lead_id)
                .join(SourceSystem)
                .where(_normalised_source_type() != "website")
            )
            if filters.source_type == "unknown":
                conditions.append(Lead.id.not_in(named_sources))
            else:
                conditions.append(
                    Lead.id.in_(
                        named_sources.where(_normalised_source_type() == filters.source_type)
                    )
                )
        return conditions

    def page(
        self, session: Session, filters: LeadFilters, *, limit: int, offset: int
    ) -> tuple[builtins.list[Lead], int]:
        """Newest first. Loads only the lead rows; list details come from the helpers below."""
        statement = select(Lead).where(*self._page_conditions(filters))
        total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        leads = builtins.list(
            session.scalars(
                statement.order_by(Lead.created_at.desc(), Lead.id).limit(limit).offset(offset)
            )
        )
        return leads, total

    def campaign_ids_for(
        self, session: Session, lead_ids: builtins.list[str]
    ) -> dict[str, builtins.list[str]]:
        found: dict[str, builtins.list[str]] = defaultdict(builtins.list)
        for lead_id, campaign_id in session.execute(
            select(LeadCampaign.lead_id, LeadCampaign.campaign_id).where(
                LeadCampaign.lead_id.in_(lead_ids)
            )
        ):
            found[lead_id].append(campaign_id)
        return found

    def source_types_for(
        self, session: Session, lead_ids: builtins.list[str]
    ) -> dict[str, builtins.list[str]]:
        found: dict[str, builtins.list[str]] = defaultdict(builtins.list)
        rows = session.execute(
            select(SourceObservation.lead_id, _normalised_source_type())
            .join(SourceSystem)
            .where(
                SourceObservation.lead_id.in_(lead_ids),
                _normalised_source_type() != "website",
                _normalised_source_type() != "",
            )
            .distinct()
            .order_by(SourceObservation.lead_id, _normalised_source_type())
        )
        for lead_id, source_type in rows:
            found[lead_id].append(source_type)
        return found

    def next_follow_ups_for(
        self, session: Session, lead_ids: builtins.list[str]
    ) -> dict[str, date]:
        rows = session.execute(
            select(FollowUp.lead_id, func.min(FollowUp.due_date))
            .where(FollowUp.lead_id.in_(lead_ids), FollowUp.status == "open")
            .group_by(FollowUp.lead_id)
        )
        return {lead_id: due for lead_id, due in rows if due is not None}

    def distinct_source_types(self, session: Session) -> builtins.list[str]:
        return builtins.list(
            session.scalars(
                select(SourceSystem.source_type)
                .join(SourceObservation)
                .where(SourceSystem.source_type != "website")
                .distinct()
                .order_by(SourceSystem.source_type)
            )
        )
