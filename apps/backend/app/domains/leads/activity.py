from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.db.models import Lead
from app.domains.leads.schemas import LeadRead


@dataclass(frozen=True)
class LeadActivity:
    occurred_at: datetime | date
    activity_type: str
    detail: str
    status: str


def lead_activity_rows(lead: Lead | LeadRead) -> list[LeadActivity]:
    rows = [
        LeadActivity(event.created_at, "stage", event.new_stage, event.reason or "")
        for event in lead.stage_events
    ]
    rows.extend(LeadActivity(note.created_at, "note", note.content, "") for note in lead.notes)
    rows.extend(
        LeadActivity(
            follow_up.created_at,
            "follow_up",
            follow_up.follow_up_type,
            f"{follow_up.status}; due {follow_up.due_date.isoformat()}",
        )
        for follow_up in lead.follow_ups
    )
    rows.extend(
        LeadActivity(
            communication.created_at,
            "communication",
            communication.channel,
            communication.sent_status,
        )
        for communication in lead.communications
    )
    return rows


def latest_activity_at(lead: Lead | LeadRead) -> datetime | None:
    values = [
        row.occurred_at
        for row in lead_activity_rows(lead)
        if isinstance(row.occurred_at, datetime)
    ]
    return max(values) if values else None
