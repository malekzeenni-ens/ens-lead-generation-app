from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent

OUTREACH_ACTIVITY_ACTIONS = (
    "outreach.draft_generated",
    "outreach.draft_edited",
    "outreach.draft_approved",
    "outreach.draft_rejected",
    "outreach.draft_reopened",
    "outreach.zoho_open_clicked",
    "outreach.zoho_open_failed",
)


class AuditRepository:
    def has_event(
        self,
        session: Session,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
    ) -> bool:
        return (
            session.scalar(
                select(AuditEvent.id)
                .where(
                    AuditEvent.entity_type == entity_type,
                    AuditEvent.entity_id == entity_id,
                    AuditEvent.action == action,
                )
                .limit(1)
            )
            is not None
        )

    def outreach_activity_events(
        self, session: Session, lead_ids: Collection[str]
    ) -> list[AuditEvent]:
        if not lead_ids:
            return []
        statement = (
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "outreach_draft",
                AuditEvent.action.in_(OUTREACH_ACTIVITY_ACTIONS),
                AuditEvent.summary["lead_id"].as_string().in_(lead_ids),
            )
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
        return list(session.scalars(statement))
