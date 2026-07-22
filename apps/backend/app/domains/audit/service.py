from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record_audit_event(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    correlation_id: str,
    summary: dict[str, Any],
    actor: str = "local_user",
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        correlation_id=correlation_id,
        summary=summary,
    )
    session.add(event)
    return event
