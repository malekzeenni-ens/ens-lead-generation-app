"""Notes, follow-ups and recorded communications on a lead.

Part of the LeadService chain (R9); methods moved unchanged.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    Communication,
    FollowUp,
    LeadNote,
)
from app.domains.audit.service import record_audit_event
from app.domains.leads.editing import LeadEditing
from app.domains.leads.schemas import (
    CommunicationCreate,
    CommunicationStatus,
    FollowUpComplete,
    FollowUpCreate,
    FollowUpStatus,
    LeadRead,
    NoteCreate,
)

logger = logging.getLogger(__name__)


class LeadOperations(LeadEditing):
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
