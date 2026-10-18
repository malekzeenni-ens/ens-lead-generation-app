"""Reading leads and the identity checks every change goes through.

Part of the LeadService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import builtins
import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    Lead,
    LeadSocialIdentity,
    OutreachActivity,
)
from app.domains.campaigns.repository import CampaignRepository
from app.domains.leads.identity import (
    social_identity,
)
from app.domains.leads.lead_read import (
    lead_to_read,
)
from app.domains.leads.repository import LeadRepository
from app.domains.leads.schemas import (
    LeadRead,
)
from app.domains.leads.suppression import (
    IdentifierHash,
    find_active_suppression,
)
from app.domains.outreach.activity import activities_by_lead

logger = logging.getLogger(__name__)


class LeadServiceBase:
    def __init__(
        self,
        repository: LeadRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
    ) -> None:
        self.repository = repository or LeadRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()

    @staticmethod
    def _outreach_events(
        session: Session, lead_ids: Sequence[str]
    ) -> dict[str, list[OutreachActivity]]:
        return activities_by_lead(session, lead_ids)

    def _get_model(self, session: Session, lead_id: str) -> Lead:
        lead = self.repository.get(session, lead_id)
        if lead is None:
            raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
        return lead

    def _reload(self, session: Session, lead_id: str) -> LeadRead:
        session.expire_all()
        stored = self.repository.get(session, lead_id)
        if stored is None:
            raise RuntimeError("Stored lead could not be reloaded")
        events = self._outreach_events(session, [lead_id])
        return lead_to_read(stored, events[lead_id])

    def _upsert_social_identity(
        self,
        session: Session,
        lead: Lead,
        value: str,
        *,
        platform: str | None = None,
        classification: str = "user_verified",
        source_url: str | None = None,
    ) -> LeadSocialIdentity:
        selected, handle, canonical = social_identity(value, platform)
        existing = self.repository.find_social_identity(session, selected, handle)
        if existing is not None:
            if existing.lead_id != lead.id:
                raise DomainError(
                    "LEAD_SOCIAL_DUPLICATE_REVIEW_REQUIRED",
                    "That social profile is already attached to another lead.",
                    status_code=409,
                    details={"candidate_lead_id": existing.lead_id},
                )
            existing.profile_url = canonical
            existing.source_url = source_url or canonical
            existing.classification = classification
            return existing
        identity = LeadSocialIdentity(
            lead_id=lead.id,
            platform=selected,
            profile_url=canonical,
            normalized_handle=handle,
            source_url=source_url or canonical,
            classification=classification,
            collected_at=datetime.now(UTC),
        )
        session.add(identity)
        return identity

    @staticmethod
    def _remove_social_identity(session: Session, lead: Lead, platform: str) -> None:
        for identity in list(lead.social_identities):
            if identity.platform == platform:
                if lead.social_profile == identity.profile_url:
                    lead.social_profile = None
                session.delete(identity)

    @staticmethod
    def _assert_identifiers_allowed(
        session: Session,
        hashes: set[IdentifierHash],
        *,
        current_lead_id: str | None = None,
    ) -> None:
        match = find_active_suppression(session, hashes, exclude_lead_id=current_lead_id)
        if match is None:
            return
        logger.info(
            "Lead change blocked by an active suppression",
            extra={
                "lead_id": current_lead_id,
                "suppression_id": match.record.id,
                "matched_identifier": match.kind.value,
            },
        )
        raise DomainError(
            "LEAD_IDENTIFIER_SUPPRESSED",
            f"This business matches an active suppression record by its {match.label}.",
            status_code=409,
            details={"matched_identifier": match.kind.value},
        )

    def list(
        self,
        session: Session,
        *,
        query: str | None = None,
        stage: str | None = None,
        suppressed: bool | None = None,
        campaign_id: str | None = None,
    ) -> builtins.list[LeadRead]:
        leads = self.repository.list(
            session,
            query=query,
            stage=stage,
            suppressed=suppressed,
            campaign_id=campaign_id,
        )
        events = self._outreach_events(session, [lead.id for lead in leads])
        return [lead_to_read(lead, events[lead.id]) for lead in leads]

    def get(self, session: Session, lead_id: str) -> LeadRead:
        lead = self._get_model(session, lead_id)
        events = self._outreach_events(session, [lead_id])
        return lead_to_read(lead, events[lead_id])
