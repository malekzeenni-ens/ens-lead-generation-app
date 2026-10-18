from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent

# Audit events outlive privacy deletion (FR-163), so they record IDs, versions, counts, enums,
# hashes and field names only (ADR-024). Personal data and free text the operator typed belong in
# the domain tables, which are deleted with the lead. A summary carrying any of these keys, at any
# depth, is refused so a regression fails loudly instead of leaking.
PERSONAL_DATA_KEYS = frozenset(
    {
        "avoid_mentioning",
        "body",
        "business_name",
        "contact_email",
        "contact_first_name",
        "contact_last_name",
        "contact_role",
        "contact_source_reference",
        "content",
        "desired_next_step",
        "email",
        "facebook_url",
        "first_name",
        "instagram_url",
        "last_name",
        "location",
        "notes",
        "offer_angle",
        "outreach_hold_reason",
        "personalisation_observation",
        "phone",
        "phone_number",
        "public_email",
        "reason",
        "recipient_email",
        "relevance_opportunity",
        "social_profile",
        "subject",
        "website",
    }
)


def _personal_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            here = f"{path}.{key}" if path else str(key)
            if str(key) in PERSONAL_DATA_KEYS:
                found.append(here)
            found.extend(_personal_keys(item, here))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_personal_keys(item, f"{path}[{index}]"))
    return found


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
    personal = _personal_keys(summary)
    if personal:
        raise ValueError(
            f"Audit event {action} must not record personal data: {', '.join(personal)}"
        )
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
