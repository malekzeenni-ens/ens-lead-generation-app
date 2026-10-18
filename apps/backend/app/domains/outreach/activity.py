"""Outreach history: a working record for the lead, and an audit event without personal data.

ADR-024. The lead's activity timeline used to be rebuilt from audit-event JSON, which forced the
audit log to hold the recipient address and the operator's reasons and kept them after the lead was
deleted. The activity row now holds them and is deleted with the lead; the audit event keeps IDs,
the version and whether a reason was given.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OutreachActivity, OutreachDraft
from app.domains.audit.service import record_audit_event

# The actions shown in a lead's outreach history.
OUTREACH_ACTIVITY_ACTIONS = (
    "outreach.draft_generated",
    "outreach.draft_edited",
    "outreach.draft_approved",
    "outreach.draft_rejected",
    "outreach.draft_reopened",
    "outreach.zoho_open_clicked",
    "outreach.zoho_open_failed",
)


def record_outreach_activity(
    session: Session,
    *,
    draft: OutreachDraft,
    action: str,
    correlation_id: str,
    version: int | None = None,
    reason: str | None = None,
    recipient_email: str | None = None,
    audit_details: dict[str, Any] | None = None,
) -> OutreachActivity:
    if action not in OUTREACH_ACTIVITY_ACTIONS:
        raise ValueError(f"{action} is not an outreach activity")
    activity = OutreachActivity(
        lead_id=draft.lead_id,
        draft_id=draft.id,
        action=action,
        version=version,
        reason=reason or None,
        recipient_email=recipient_email,
    )
    session.add(activity)
    summary: dict[str, Any] = {"lead_id": draft.lead_id}
    if version is not None:
        summary["version"] = version
    if reason is not None:
        summary["reason_provided"] = bool(reason)
    summary.update(audit_details or {})
    record_audit_event(
        session,
        action=action,
        entity_type="outreach_draft",
        entity_id=draft.id,
        correlation_id=correlation_id,
        summary=summary,
    )
    return activity


def activities_by_lead(
    session: Session, lead_ids: Sequence[str]
) -> dict[str, list[OutreachActivity]]:
    by_lead: dict[str, list[OutreachActivity]] = {lead_id: [] for lead_id in lead_ids}
    if not lead_ids:
        return by_lead
    rows = session.scalars(
        select(OutreachActivity)
        .where(OutreachActivity.lead_id.in_(list(lead_ids)))
        .order_by(OutreachActivity.created_at, OutreachActivity.id)
    )
    for activity in rows:
        by_lead[activity.lead_id].append(activity)
    return by_lead
