"""Suppression, privacy deletion and export.

Part of the LeadService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import builtins
import csv
import io
import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.csv_safety import safe_csv_cell
from app.core.errors import DomainError
from app.db.models import (
    LeadStageEvent,
    ShortlistItem,
    SuppressionRecord,
)
from app.domains.audit.service import record_audit_event
from app.domains.leads.activity import lead_activity_rows
from app.domains.leads.identity import (
    lead_identifier_hash,
)
from app.domains.leads.operations import LeadOperations
from app.domains.leads.schemas import (
    FollowUpStatus,
    LeadDeleteResult,
    LeadRead,
    PipelineStage,
    SuppressionCreate,
)
from app.domains.leads.suppression import (
    lead_identifier_hashes,
    record_identifiers,
)
from app.domains.outreach.state import invalidate_approved_drafts

logger = logging.getLogger(__name__)


class LeadPrivacy(LeadOperations):
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
        session.flush()
        record_identifiers(record, lead_identifier_hashes(session, lead))
        lead.suppressed = True
        invalidated_drafts = invalidate_approved_drafts(
            session,
            lead.id,
            "Lead was suppressed after draft approval.",
        )
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
                "invalidated_outreach_drafts": invalidated_drafts,
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
        active_records = [record for record in lead.suppression_records if record.active]
        retained = bool(active_records)
        identifier_hash = lead_identifier_hash(lead.business_name, lead.location)
        if active_records:
            # Capture identifiers learned since the suppression, before the lead is gone.
            current = lead_identifier_hashes(session, lead)
            for record in active_records:
                record_identifiers(record, current)
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
                "contact_first_name": lead.contact_first_name,
                "contact_last_name": lead.contact_last_name,
                "contact_role": lead.contact_role,
                "contact_email": lead.contact_email,
                "contact_source_reference": lead.contact_source_reference,
                "personalisation_observation": lead.personalisation_observation,
                "relevance_opportunity": lead.relevance_opportunity,
                "offer_angle": lead.offer_angle,
                "desired_next_step": lead.desired_next_step,
                "avoid_mentioning": lead.avoid_mentioning,
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
            activities: builtins.list[tuple[datetime | date, str, str, str]] = [
                (row.occurred_at, row.activity_type, row.detail, row.status)
                for row in lead_activity_rows(lead)
            ]
            activities.extend(
                (
                    activity.created_at,
                    "outreach_draft",
                    activity.action.removeprefix("outreach."),
                    (
                        f"version {activity.version}"
                        if activity.version is not None
                        else (activity.reason or "")
                    ),
                )
                for activity in lead.outreach_activities
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
            "contact_first_name",
            "contact_last_name",
            "contact_role",
            "contact_email",
            "contact_source_reference",
            "personalisation_observation",
            "relevance_opportunity",
            "offer_angle",
            "desired_next_step",
            "avoid_mentioning",
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
            writer.writerow({key: safe_csv_cell(row.get(key)) for key in fieldnames})
        return output.getvalue()
