"""Move outreach history out of the audit log and remove personal data from audit events.

ADR-024 and decision D2. A lead's outreach timeline was rebuilt from audit-event JSON, so audit
events held recipient addresses and the operator's reasons and kept them after the lead was
deleted (FR-163). This revision:

1. adds `outreach_draft.zoho_opened_at` and the `outreach_activity` table;
2. backfills both from existing audit events, keeping each event's ID and time;
3. scrubs personal data from every historic audit summary, leaving IDs, versions, counts, field
   names and whether a reason was given.

Step 3 cannot be undone. `app.db.migrations.run_migrations` copies an existing database beside
itself before applying any pending revision (`<name>.pre-upgrade-<revision>-<UTC time>.sqlite3`);
that copy still holds the personal data removed here and should be deleted once the upgraded app
has been checked.

The rules below are a frozen copy of the application's as of this revision.

Revision ID: 0018_outreach_activity
Revises: 0017_suppression_identifiers
Create Date: 2026-10-18
"""

import json
import logging
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0018_outreach_activity"
down_revision: str | None = "0017_suppression_identifiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

_ACTIVITY_ACTIONS = (
    "outreach.draft_generated",
    "outreach.draft_edited",
    "outreach.draft_approved",
    "outreach.draft_rejected",
    "outreach.draft_reopened",
    "outreach.zoho_open_clicked",
    "outreach.zoho_open_failed",
)
_PERSONAL_KEYS = frozenset(
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
_AUDITED_LEAD_VALUE_FIELDS = frozenset(
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


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key == "reason":
                cleaned["reason_provided"] = bool(item)
            elif key not in _PERSONAL_KEYS:
                cleaned[key] = _scrub(item)
        return cleaned
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _minimised(action: str, summary: dict[str, Any]) -> dict[str, Any]:
    if action == "lead.updated" and ("before" in summary or "after" in summary):
        before = summary.get("before") or {}
        after = summary.get("after") or {}
        fields = sorted(set(before) | set(after))
        rest = {key: item for key, item in summary.items() if key not in {"before", "after"}}
        return _scrub(
            {
                **rest,
                "changed_fields": fields,
                "values": {
                    field: {"before": before.get(field), "after": after.get(field)}
                    for field in fields
                    if field in _AUDITED_LEAD_VALUE_FIELDS
                },
            }
        )
    return _scrub(summary)


def _as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        decoded = json.loads(raw)
        return decoded if isinstance(decoded, dict) else {}
    return {}


def upgrade() -> None:
    with op.batch_alter_table("outreach_draft") as batch:
        batch.add_column(sa.Column("zoho_opened_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "outreach_activity",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "lead_id",
            sa.String(length=36),
            sa.ForeignKey("lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "draft_id",
            sa.String(length=36),
            sa.ForeignKey("outreach_draft.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outreach_activity_lead_created", "outreach_activity", ["lead_id", "created_at"]
    )

    connection = op.get_bind()
    drafts = {
        str(row.id): str(row.lead_id)
        for row in connection.execute(sa.text("SELECT id, lead_id FROM outreach_draft"))
    }
    events = connection.execute(
        sa.text("SELECT id, action, entity_type, entity_id, summary, created_at FROM audit_event")
    ).all()

    activities: list[dict[str, Any]] = []
    first_opened: dict[str, Any] = {}
    scrubbed: list[dict[str, Any]] = []
    for event in events:
        summary = _as_dict(event.summary)
        if event.entity_type == "outreach_draft" and event.action in _ACTIVITY_ACTIONS:
            lead_id = drafts.get(str(event.entity_id))
            if lead_id is not None:
                version = summary.get("version")
                reason = summary.get("reason")
                recipient = summary.get("recipient_email")
                activities.append(
                    {
                        "id": event.id,
                        "lead_id": lead_id,
                        "draft_id": event.entity_id,
                        "action": event.action,
                        "version": version if isinstance(version, int) else None,
                        "reason": reason if isinstance(reason, str) and reason else None,
                        "recipient_email": (
                            recipient if isinstance(recipient, str) and recipient else None
                        ),
                        "created_at": event.created_at,
                    }
                )
                if event.action == "outreach.zoho_open_clicked":
                    current = first_opened.get(str(event.entity_id))
                    if current is None or str(event.created_at) < str(current):
                        first_opened[str(event.entity_id)] = event.created_at
        minimised = _minimised(str(event.action), summary)
        if minimised != summary:
            scrubbed.append({"id": event.id, "summary": json.dumps(minimised)})

    if activities:
        connection.execute(
            sa.text(
                "INSERT INTO outreach_activity (id, lead_id, draft_id, action, version, reason, "
                "recipient_email, created_at) VALUES (:id, :lead_id, :draft_id, :action, "
                ":version, :reason, :recipient_email, :created_at)"
            ),
            activities,
        )
    for draft_id, opened_at in first_opened.items():
        connection.execute(
            sa.text("UPDATE outreach_draft SET zoho_opened_at = :opened WHERE id = :id"),
            {"opened": opened_at, "id": draft_id},
        )
    if scrubbed:
        connection.execute(
            sa.text("UPDATE audit_event SET summary = :summary WHERE id = :id"), scrubbed
        )
        logger.info("Removed personal data from %d audit events", len(scrubbed))


def downgrade() -> None:
    # The audit scrub is not reversed; restore the pre-0018 copy if the data is needed.
    op.drop_index("ix_outreach_activity_lead_created", table_name="outreach_activity")
    op.drop_table("outreach_activity")
    with op.batch_alter_table("outreach_draft") as batch:
        batch.drop_column("zoho_opened_at")
