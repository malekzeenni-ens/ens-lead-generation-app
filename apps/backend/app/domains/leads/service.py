from __future__ import annotations

import builtins
import csv
import hashlib
import io
import re
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    Communication,
    FollowUp,
    Lead,
    LeadNote,
    LeadSocialIdentity,
    LeadStageEvent,
    ShortlistItem,
    SourceObservation,
    SourceSystem,
    SuppressionRecord,
)
from app.domains.audit.service import record_audit_event
from app.domains.campaigns.repository import CampaignRepository
from app.domains.leads.identity import social_identity
from app.domains.leads.repository import LeadRepository
from app.domains.leads.schemas import (
    CommunicationCreate,
    CommunicationRead,
    CommunicationStatus,
    FollowUpComplete,
    FollowUpCreate,
    FollowUpRead,
    FollowUpStatus,
    LeadCreate,
    LeadDeleteResult,
    LeadNoteRead,
    LeadRead,
    LeadUpdate,
    NoteCreate,
    PipelineStage,
    SocialIdentityRead,
    SourceObservationRead,
    StageChange,
    StageEventRead,
    SuppressionCreate,
    SuppressionRead,
)


def normalize_business_name(value: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip().split()
    return " ".join(words)


def lead_identifier_hash(business_name: str, location: str) -> str:
    canonical = f"{normalize_business_name(business_name)}|{location.casefold().strip()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _audit_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def lead_to_read(lead: Lead) -> LeadRead:
    sources = [
        SourceObservationRead(
            id=observation.id,
            source_name=observation.source_system.name,
            source_type=observation.source_system.source_type,
            field_name=observation.field_name,
            observed_value=observation.observed_value,
            classification=observation.classification,
            source_url=observation.source_url,
            collection_method=observation.collection_method,
            collected_at=observation.collected_at,
        )
        for observation in sorted(lead.observations, key=lambda item: item.collected_at)
    ]
    events = [
        StageEventRead.model_validate(event)
        for event in sorted(lead.stage_events, key=lambda item: item.created_at)
    ]
    notes = [
        LeadNoteRead.model_validate(note)
        for note in sorted(lead.notes, key=lambda item: item.created_at)
    ]
    follow_ups = [
        FollowUpRead.model_validate(follow_up)
        for follow_up in sorted(lead.follow_ups, key=lambda item: (item.due_date, item.created_at))
    ]
    communications = [
        CommunicationRead.model_validate(communication)
        for communication in sorted(lead.communications, key=lambda item: item.created_at)
    ]
    suppressions = [
        SuppressionRead.model_validate(record)
        for record in sorted(lead.suppression_records, key=lambda item: item.effective_at)
    ]
    return LeadRead(
        id=lead.id,
        business_name=lead.business_name,
        segment=lead.segment,
        location=lead.location,
        website=lead.website,
        social_profile=lead.social_profile,
        phone_number=lead.phone_number,
        public_email=lead.public_email,
        social_identities=[
            SocialIdentityRead.model_validate(identity)
            for identity in sorted(lead.social_identities, key=lambda item: item.platform)
        ],
        contact_classification=lead.contact_classification,
        pipeline_stage=lead.pipeline_stage,
        suppressed=lead.suppressed,
        estimated_order_value=lead.estimated_order_value,
        quote_value=lead.quote_value,
        won_value=lead.won_value,
        potential_recurrence=lead.potential_recurrence,
        lost_reason=lead.lost_reason,
        mock_up_status=lead.mock_up_status,
        sample_status=lead.sample_status,
        quote_status=lead.quote_status,
        retention_review_date=lead.retention_review_date,
        current_score=lead.current_score,
        score_updated_at=lead.score_updated_at,
        campaign_ids=[link.campaign_id for link in lead.campaigns],
        sources=sources,
        stage_events=events,
        notes=notes,
        follow_ups=follow_ups,
        communications=communications,
        suppression_records=suppressions,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


class LeadService:
    def __init__(
        self,
        repository: LeadRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
    ) -> None:
        self.repository = repository or LeadRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()

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
        return lead_to_read(stored)

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

    def _assert_identifier_allowed(
        self,
        session: Session,
        business_name: str,
        location: str,
        *,
        current_lead_id: str | None = None,
    ) -> None:
        identifier_hash = lead_identifier_hash(business_name, location)
        suppressed = self.repository.active_suppression_by_hash(session, identifier_hash)
        if suppressed is not None and (
            current_lead_id is None or suppressed.lead_id != current_lead_id
        ):
            raise DomainError(
                "LEAD_IDENTIFIER_SUPPRESSED",
                "This business and location match an active suppression record.",
                status_code=409,
            )

    def create(self, session: Session, data: LeadCreate, correlation_id: str) -> LeadRead:
        campaign = self.campaign_repository.get(session, data.campaign_id)
        if campaign is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)

        self._assert_identifier_allowed(session, data.business_name, data.location)
        normalized_name = normalize_business_name(data.business_name)
        duplicate = self.repository.find_exact(session, normalized_name, data.location)
        if duplicate is not None:
            raise DomainError(
                "LEAD_DUPLICATE_REVIEW_REQUIRED",
                "A lead with the same normalised name and location requires review.",
                status_code=409,
                details={"candidate_lead_id": duplicate.id},
            )

        lead = Lead(
            business_name=data.business_name,
            normalized_name=normalized_name,
            segment=data.segment,
            location=data.location,
            website=str(data.website) if data.website else None,
            social_profile=str(data.social_profile or data.instagram_url or data.facebook_url)
            if (data.social_profile or data.instagram_url or data.facebook_url)
            else None,
            phone_number=data.phone_number,
            public_email=data.public_email.casefold() if data.public_email else None,
            contact_classification=data.contact_classification.value,
            pipeline_stage=PipelineStage.NEW.value,
        )
        self.repository.add(session, lead)
        session.flush()
        for platform, profile in (
            (None, data.social_profile),
            ("instagram", data.instagram_url),
            ("facebook", data.facebook_url),
        ):
            if profile:
                self._upsert_social_identity(
                    session,
                    lead,
                    str(profile),
                    platform=platform,
                    source_url=str(data.source.source_url) if data.source.source_url else None,
                )
        self.repository.link_campaign(session, lead.id, data.campaign_id)

        source_system = session.scalar(
            select(SourceSystem).where(SourceSystem.name == data.source.name)
        )
        if source_system is None:
            source_system = SourceSystem(
                name=data.source.name,
                source_type=data.source.source_type.value,
            )
            session.add(source_system)
            session.flush()

        session.add(
            SourceObservation(
                lead_id=lead.id,
                source_system_id=source_system.id,
                field_name="business_identity",
                observed_value=data.business_name,
                classification=data.source.classification.value,
                source_url=str(data.source.source_url) if data.source.source_url else None,
                collection_method="manual_entry",
                collected_at=data.source.collected_at,
            )
        )
        for field_name, observed_value in (
            ("public_phone", data.phone_number),
            ("public_email", data.public_email),
        ):
            if observed_value:
                session.add(
                    SourceObservation(
                        lead_id=lead.id,
                        source_system_id=source_system.id,
                        field_name=field_name,
                        observed_value=observed_value,
                        classification=data.source.classification.value,
                        source_url=str(data.source.source_url) if data.source.source_url else None,
                        collection_method="manual_entry",
                        collected_at=data.source.collected_at,
                    )
                )
        session.add(
            LeadStageEvent(
                lead_id=lead.id,
                previous_stage=None,
                new_stage=PipelineStage.NEW.value,
                actor="local_user",
                reason="Manual lead entry",
            )
        )
        record_audit_event(
            session,
            action="lead.created",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "business_name": lead.business_name,
                "campaign_id": data.campaign_id,
                "source_type": data.source.source_type.value,
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    def list(
        self,
        session: Session,
        *,
        query: str | None = None,
        stage: str | None = None,
        suppressed: bool | None = None,
        campaign_id: str | None = None,
    ) -> list[LeadRead]:
        leads = self.repository.list(
            session,
            query=query,
            stage=stage,
            suppressed=suppressed,
            campaign_id=campaign_id,
        )
        return [lead_to_read(lead) for lead in leads]

    def get(self, session: Session, lead_id: str) -> LeadRead:
        return lead_to_read(self._get_model(session, lead_id))

    def update(
        self,
        session: Session,
        lead_id: str,
        data: LeadUpdate,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        changes = data.model_dump(exclude_unset=True)
        social_changes = {
            field: changes.pop(field)
            for field in ("instagram_url", "facebook_url")
            if field in changes
        }
        next_name = str(changes.get("business_name", lead.business_name))
        next_location = str(changes.get("location", lead.location))
        if "business_name" in changes or "location" in changes:
            self._assert_identifier_allowed(
                session,
                next_name,
                next_location,
                current_lead_id=lead.id,
            )
            duplicate = self.repository.find_exact(
                session, normalize_business_name(next_name), next_location
            )
            if duplicate is not None and duplicate.id != lead.id:
                raise DomainError(
                    "LEAD_DUPLICATE_REVIEW_REQUIRED",
                    "A lead with the same normalised name and location requires review.",
                    status_code=409,
                    details={"candidate_lead_id": duplicate.id},
                )

        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for field, value in changes.items():
            before[field] = _audit_value(getattr(lead, field))
            stored_value = value.value if isinstance(value, Enum) else value
            if field in {"website", "social_profile"} and stored_value is not None:
                stored_value = str(stored_value)
            if field == "public_email" and stored_value:
                stored_value = str(stored_value).casefold()
            setattr(lead, field, stored_value)
            after[field] = _audit_value(stored_value)
            if field == "social_profile" and stored_value:
                self._upsert_social_identity(session, lead, stored_value)
        for field, value in social_changes.items():
            platform = field.removesuffix("_url")
            current = next(
                (
                    identity.profile_url
                    for identity in lead.social_identities
                    if identity.platform == platform
                ),
                None,
            )
            before[field] = current
            if value is None:
                self._remove_social_identity(session, lead, platform)
                after[field] = None
            else:
                identity = self._upsert_social_identity(
                    session, lead, str(value), platform=platform
                )
                lead.social_profile = lead.social_profile or identity.profile_url
                after[field] = identity.profile_url
        if "business_name" in changes:
            lead.normalized_name = normalize_business_name(lead.business_name)

        record_audit_event(
            session,
            action="lead.updated",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={"before": before, "after": after},
        )
        session.commit()
        return self._reload(session, lead.id)

    def change_stage(
        self,
        session: Session,
        lead_id: str,
        data: StageChange,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        if lead.suppressed and data.stage is not PipelineStage.DO_NOT_CONTACT:
            raise DomainError(
                "SUPPRESSED_LEAD_STAGE_BLOCKED",
                "Lift suppression before moving this lead out of Do Not Contact.",
                status_code=409,
            )
        if lead.pipeline_stage == data.stage.value:
            raise DomainError(
                "LEAD_STAGE_UNCHANGED",
                "The lead is already in this pipeline stage.",
                status_code=409,
            )
        previous_stage = lead.pipeline_stage
        lead.pipeline_stage = data.stage.value
        session.add(
            LeadStageEvent(
                lead_id=lead.id,
                previous_stage=previous_stage,
                new_stage=data.stage.value,
                actor="local_user",
                reason=data.reason,
            )
        )
        record_audit_event(
            session,
            action="lead.stage_changed",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "previous_stage": previous_stage,
                "new_stage": data.stage.value,
                "reason": data.reason,
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    def add_note(
        self,
        session: Session,
        lead_id: str,
        data: NoteCreate,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        note = LeadNote(lead_id=lead.id, content=data.content, actor="local_user")
        self.repository.add_note(session, note)
        session.flush()
        record_audit_event(
            session,
            action="lead.note_added",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={"note_id": note.id},
        )
        session.commit()
        return self._reload(session, lead.id)

    def add_follow_up(
        self,
        session: Session,
        lead_id: str,
        data: FollowUpCreate,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        if lead.suppressed:
            raise DomainError(
                "SUPPRESSED_LEAD_FOLLOW_UP_BLOCKED",
                "New follow-ups cannot be created for a suppressed lead.",
                status_code=409,
            )
        follow_up = FollowUp(
            lead_id=lead.id,
            follow_up_type=data.follow_up_type.value,
            due_date=data.due_date,
            status=FollowUpStatus.OPEN.value,
            notes=data.notes,
        )
        self.repository.add_follow_up(session, follow_up)
        session.flush()
        record_audit_event(
            session,
            action="lead.follow_up_created",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "follow_up_id": follow_up.id,
                "type": follow_up.follow_up_type,
                "due_date": follow_up.due_date.isoformat(),
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    def complete_follow_up(
        self,
        session: Session,
        lead_id: str,
        follow_up_id: str,
        data: FollowUpComplete,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        follow_up = self.repository.get_follow_up(session, lead.id, follow_up_id)
        if follow_up is None:
            raise DomainError("FOLLOW_UP_NOT_FOUND", "Follow-up not found.", status_code=404)
        if follow_up.status != FollowUpStatus.OPEN.value:
            raise DomainError(
                "FOLLOW_UP_ALREADY_CLOSED",
                "Only an open follow-up can be completed.",
                status_code=409,
            )
        if data.next_follow_up is not None and lead.suppressed:
            raise DomainError(
                "SUPPRESSED_LEAD_FOLLOW_UP_BLOCKED",
                "A next follow-up cannot be created for a suppressed lead.",
                status_code=409,
            )

        follow_up.status = FollowUpStatus.COMPLETED.value
        follow_up.completed_at = datetime.now(UTC)
        next_follow_up_id: str | None = None
        if data.next_follow_up is not None:
            next_follow_up = FollowUp(
                lead_id=lead.id,
                follow_up_type=data.next_follow_up.follow_up_type.value,
                due_date=data.next_follow_up.due_date,
                status=FollowUpStatus.OPEN.value,
                notes=data.next_follow_up.notes,
            )
            self.repository.add_follow_up(session, next_follow_up)
            session.flush()
            next_follow_up_id = next_follow_up.id
        record_audit_event(
            session,
            action="lead.follow_up_completed",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "follow_up_id": follow_up.id,
                "next_follow_up_id": next_follow_up_id,
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    def add_communication(
        self,
        session: Session,
        lead_id: str,
        data: CommunicationCreate,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        if lead.suppressed and data.sent_status is CommunicationStatus.SENT:
            raise DomainError(
                "SUPPRESSED_LEAD_COMMUNICATION_BLOCKED",
                "A sent communication cannot be recorded for a suppressed lead.",
                status_code=409,
            )
        communication = Communication(
            lead_id=lead.id,
            channel=data.channel.value,
            subject=data.subject,
            content=data.content,
            sent_status=data.sent_status.value,
            sent_at=datetime.now(UTC) if data.sent_status is CommunicationStatus.SENT else None,
            user_confirmed=data.user_confirmed,
            external_message_id=data.external_message_id,
            response_status=data.response_status.value,
            draft_status="not_applicable",
            approval_status="manual_confirmed" if data.user_confirmed else "not_applicable",
        )
        self.repository.add_communication(session, communication)
        session.flush()
        record_audit_event(
            session,
            action="lead.communication_recorded",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "communication_id": communication.id,
                "channel": communication.channel,
                "sent_status": communication.sent_status,
                "user_confirmed": communication.user_confirmed,
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    def suppress(
        self,
        session: Session,
        lead_id: str,
        data: SuppressionCreate,
        correlation_id: str,
    ) -> LeadRead:
        lead = self._get_model(session, lead_id)
        if lead.suppressed:
            raise DomainError(
                "LEAD_ALREADY_SUPPRESSED",
                "This lead already has an active suppression.",
                status_code=409,
            )
        now = datetime.now(UTC)
        record = SuppressionRecord(
            lead_id=lead.id,
            identifier_hash=lead_identifier_hash(lead.business_name, lead.location),
            suppression_type=data.suppression_type.value,
            reason=data.reason,
            source=data.source,
            notes=data.notes,
            active=True,
            effective_at=now,
        )
        session.add(record)
        lead.suppressed = True
        cancelled_follow_ups = 0
        for follow_up in lead.follow_ups:
            if follow_up.status == FollowUpStatus.OPEN.value:
                follow_up.status = FollowUpStatus.CANCELLED.value
                follow_up.completed_at = now
                cancelled_follow_ups += 1
        removed_shortlist_items = 0
        active_shortlist_items = session.scalars(
            select(ShortlistItem).where(
                ShortlistItem.lead_id == lead.id,
                ShortlistItem.decision.in_(["recommended", "approved"]),
            )
        )
        for shortlist_item in active_shortlist_items:
            shortlist_item.decision = "suppressed"
            shortlist_item.decided_at = now
            removed_shortlist_items += 1
        if lead.pipeline_stage != PipelineStage.DO_NOT_CONTACT.value:
            previous_stage = lead.pipeline_stage
            lead.pipeline_stage = PipelineStage.DO_NOT_CONTACT.value
            session.add(
                LeadStageEvent(
                    lead_id=lead.id,
                    previous_stage=previous_stage,
                    new_stage=PipelineStage.DO_NOT_CONTACT.value,
                    actor="local_user",
                    reason=data.reason,
                )
            )
        session.flush()
        record_audit_event(
            session,
            action="lead.suppressed",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={
                "suppression_id": record.id,
                "type": record.suppression_type,
                "cancelled_follow_ups": cancelled_follow_ups,
                "removed_shortlist_items": removed_shortlist_items,
            },
        )
        session.commit()
        return self._reload(session, lead.id)

    def lift_suppression(self, session: Session, lead_id: str, correlation_id: str) -> LeadRead:
        lead = self._get_model(session, lead_id)
        active_records = [record for record in lead.suppression_records if record.active]
        if not lead.suppressed or not active_records:
            raise DomainError(
                "LEAD_NOT_SUPPRESSED",
                "This lead has no active suppression.",
                status_code=409,
            )
        lifted_at = datetime.now(UTC)
        for record in active_records:
            record.active = False
            record.lifted_at = lifted_at
        lead.suppressed = False
        record_audit_event(
            session,
            action="lead.suppression_lifted",
            entity_type="lead",
            entity_id=lead.id,
            correlation_id=correlation_id,
            summary={"suppression_ids": [record.id for record in active_records]},
        )
        session.commit()
        return self._reload(session, lead.id)

    def delete(self, session: Session, lead_id: str, correlation_id: str) -> LeadDeleteResult:
        lead = self._get_model(session, lead_id)
        retained = any(record.active for record in lead.suppression_records)
        identifier_hash = lead_identifier_hash(lead.business_name, lead.location)
        session.delete(lead)
        record_audit_event(
            session,
            action="lead.deleted",
            entity_type="lead",
            entity_id=lead_id,
            correlation_id=correlation_id,
            summary={
                "identifier_hash": identifier_hash,
                "suppression_evidence_retained": retained,
            },
        )
        session.commit()
        return LeadDeleteResult(deleted=True, suppression_evidence_retained=retained)

    def export_json(self, session: Session) -> builtins.list[dict[str, Any]]:
        return [lead.model_dump(mode="json") for lead in self.list(session)]

    def export_csv(self, session: Session) -> str:
        rows: builtins.list[dict[str, Any]] = []
        for lead in self.list(session):
            base = {
                "lead_id": lead.id,
                "business_name": lead.business_name,
                "segment": lead.segment,
                "location": lead.location,
                "website": lead.website,
                "social_profile": lead.social_profile,
                "phone_number": lead.phone_number,
                "public_email": lead.public_email,
                "instagram_url": next(
                    (
                        item.profile_url
                        for item in lead.social_identities
                        if item.platform == "instagram"
                    ),
                    None,
                ),
                "facebook_url": next(
                    (
                        item.profile_url
                        for item in lead.social_identities
                        if item.platform == "facebook"
                    ),
                    None,
                ),
                "contact_classification": lead.contact_classification,
                "pipeline_stage": lead.pipeline_stage,
                "suppressed": lead.suppressed,
                "estimated_order_value": lead.estimated_order_value,
                "quote_value": lead.quote_value,
                "won_value": lead.won_value,
            }
            activities: builtins.list[tuple[datetime | date, str, str, str]] = []
            activities.extend(
                (event.created_at, "stage", event.new_stage, event.reason or "")
                for event in lead.stage_events
            )
            activities.extend((note.created_at, "note", note.content, "") for note in lead.notes)
            activities.extend(
                (
                    follow_up.created_at,
                    "follow_up",
                    follow_up.follow_up_type,
                    f"{follow_up.status}; due {follow_up.due_date.isoformat()}",
                )
                for follow_up in lead.follow_ups
            )
            activities.extend(
                (
                    communication.created_at,
                    "communication",
                    communication.channel,
                    communication.sent_status,
                )
                for communication in lead.communications
            )
            activities.extend(
                (
                    suppression.effective_at,
                    "suppression",
                    suppression.suppression_type,
                    "active" if suppression.active else "lifted",
                )
                for suppression in lead.suppression_records
            )
            if not activities:
                activities.append((lead.created_at, "lead", "created", ""))
            for occurred_at, activity_type, detail, activity_status in activities:
                rows.append(
                    {
                        **base,
                        "activity_at": occurred_at.isoformat(),
                        "activity_type": activity_type,
                        "activity_detail": detail,
                        "activity_status": activity_status,
                    }
                )

        fieldnames = [
            "lead_id",
            "business_name",
            "segment",
            "location",
            "website",
            "social_profile",
            "phone_number",
            "public_email",
            "instagram_url",
            "facebook_url",
            "contact_classification",
            "pipeline_stage",
            "suppressed",
            "estimated_order_value",
            "quote_value",
            "won_value",
            "activity_at",
            "activity_type",
            "activity_detail",
            "activity_status",
        ]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: self._safe_csv_cell(row.get(key)) for key in fieldnames})
        return output.getvalue()

    @staticmethod
    def _safe_csv_cell(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if value.lstrip().startswith(("=", "+", "-", "@")):
            return f"'{value}"
        return value
