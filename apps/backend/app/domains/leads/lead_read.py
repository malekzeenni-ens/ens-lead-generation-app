"""A lead's API shape, and the field sets audit and suppression checks use (R9 split)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from enum import Enum
from typing import Any

from app.db.models import (
    Lead,
    OutreachActivity,
)
from app.domains.leads.schemas import (
    CommunicationRead,
    FollowUpRead,
    LeadNoteRead,
    LeadRead,
    OutreachActivityRead,
    SocialIdentityRead,
    SourceObservationRead,
    StageEventRead,
    SuppressionRead,
)


def _audit_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def _outreach_activity_to_read(activity: OutreachActivity) -> OutreachActivityRead:
    return OutreachActivityRead(
        id=activity.id,
        draft_id=activity.draft_id,
        action=activity.action,
        version=activity.version,
        reason=activity.reason or None,
        recipient_email=activity.recipient_email or None,
        created_at=activity.created_at,
    )


def lead_to_read(lead: Lead, outreach_events: Sequence[OutreachActivity] = ()) -> LeadRead:
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
        contact_first_name=lead.contact_first_name,
        contact_last_name=lead.contact_last_name,
        contact_role=lead.contact_role,
        contact_email=lead.contact_email,
        contact_source_reference=lead.contact_source_reference,
        personalisation_observation=lead.personalisation_observation,
        relevance_opportunity=lead.relevance_opportunity,
        offer_angle=lead.offer_angle,
        desired_next_step=lead.desired_next_step,
        avoid_mentioning=lead.avoid_mentioning,
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
        outreach_hold_until=lead.outreach_hold_until,
        outreach_hold_reason=lead.outreach_hold_reason,
        current_score=lead.current_score,
        score_updated_at=lead.score_updated_at,
        campaign_ids=[link.campaign_id for link in lead.campaigns],
        sources=sources,
        stage_events=events,
        notes=notes,
        follow_ups=follow_ups,
        communications=communications,
        outreach_activities=[_outreach_activity_to_read(event) for event in outreach_events],
        suppression_records=suppressions,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


# Lead fields a suppression identifies a business by; changing any of them re-checks suppressions.
_IDENTIFIER_FIELDS = frozenset(
    {
        "business_name",
        "location",
        "website",
        "phone_number",
        "public_email",
        "contact_email",
        "social_profile",
    }
)


# Structured, non-personal lead fields whose before/after values the audit event records. Any other
# changed field is recorded by name only (ADR-024).
_AUDITED_VALUE_FIELDS = frozenset(
    {
        "contact_classification",
        "estimated_order_value",
        "lost_reason",
        "mock_up_status",
        "outreach_hold_until",
        "potential_recurrence",
        "quote_status",
        "quote_value",
        "retention_review_date",
        "sample_status",
        "segment",
        "won_value",
    }
)
