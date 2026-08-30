from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Lead
from app.domains.leads.activity import latest_activity_at
from app.domains.leads.repository import _LEAD_OPTIONS
from app.domains.leads.schemas import PipelineStage

_INACTIVE_STAGES = {
    PipelineStage.WON.value,
    PipelineStage.LOST.value,
    PipelineStage.NOT_SUITABLE.value,
    PipelineStage.DO_NOT_CONTACT.value,
}
ACTIVE_STAGES = {stage.value for stage in PipelineStage} - _INACTIVE_STAGES


def find_stalled_leads(
    session: Session,
    *,
    stale_after_days: int,
    limit: int,
) -> list[tuple[Lead, int]]:
    today = date.today()
    candidates = session.scalars(
        select(Lead)
        .where(
            Lead.suppressed.is_(False),
            Lead.pipeline_stage.in_(ACTIVE_STAGES),
        )
        .options(*_LEAD_OPTIONS)
    ).unique()
    results: list[tuple[Lead, int]] = []
    for lead in candidates:
        last_activity = latest_activity_at(lead)
        days_stale = (
            (datetime.now(UTC).date() - last_activity.date()).days
            if last_activity
            else stale_after_days
        )
        hold_triggered = (
            lead.outreach_hold_until is not None and lead.outreach_hold_until <= today
        )
        retention_triggered = (
            lead.retention_review_date is not None and lead.retention_review_date <= today
        )
        if hold_triggered or retention_triggered or days_stale >= stale_after_days:
            results.append((lead, days_stale))
    results.sort(key=lambda pair: (-(pair[0].current_score or 0), -pair[1], pair[0].id))
    return results[:limit]
