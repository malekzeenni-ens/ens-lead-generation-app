"""Add local CRM operations.

Revision ID: 0002_local_crm
Revises: 0001_local_core
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_local_crm"
down_revision: str | None = "0001_local_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lead", sa.Column("estimated_order_value", sa.Float(), nullable=True))
    op.add_column("lead", sa.Column("quote_value", sa.Float(), nullable=True))
    op.add_column("lead", sa.Column("won_value", sa.Float(), nullable=True))
    op.add_column("lead", sa.Column("potential_recurrence", sa.String(length=100), nullable=True))
    op.add_column("lead", sa.Column("lost_reason", sa.String(length=100), nullable=True))
    op.add_column(
        "lead",
        sa.Column("mock_up_status", sa.String(length=40), nullable=False, server_default="not_offered"),
    )
    op.add_column(
        "lead",
        sa.Column("sample_status", sa.String(length=40), nullable=False, server_default="not_applicable"),
    )
    op.add_column(
        "lead",
        sa.Column("quote_status", sa.String(length=40), nullable=False, server_default="not_requested"),
    )
    op.add_column("lead", sa.Column("retention_review_date", sa.Date(), nullable=True))

    op.create_table(
        "lead_note",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_note_lead_time", "lead_note", ["lead_id", "created_at"])

    op.create_table(
        "follow_up",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("follow_up_type", sa.String(length=40), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_follow_up_lead_due", "follow_up", ["lead_id", "due_date"])
    op.create_index("ix_follow_up_status_due", "follow_up", ["status", "due_date"])

    op.create_table(
        "communication",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("draft_status", sa.String(length=30), nullable=False),
        sa.Column("approval_status", sa.String(length=30), nullable=False),
        sa.Column("sent_status", sa.String(length=30), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("external_message_id", sa.String(length=300), nullable=True),
        sa.Column("response_status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_communication_lead_time", "communication", ["lead_id", "created_at"])

    op.create_table(
        "suppression_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("identifier_hash", sa.String(length=64), nullable=False),
        sa.Column("suppression_type", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_suppression_identifier_active",
        "suppression_record",
        ["identifier_hash", "active"],
    )
    op.create_index("ix_suppression_lead_time", "suppression_record", ["lead_id", "effective_at"])

    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_setting")
    op.drop_index("ix_suppression_lead_time", table_name="suppression_record")
    op.drop_index("ix_suppression_identifier_active", table_name="suppression_record")
    op.drop_table("suppression_record")
    op.drop_index("ix_communication_lead_time", table_name="communication")
    op.drop_table("communication")
    op.drop_index("ix_follow_up_status_due", table_name="follow_up")
    op.drop_index("ix_follow_up_lead_due", table_name="follow_up")
    op.drop_table("follow_up")
    op.drop_index("ix_lead_note_lead_time", table_name="lead_note")
    op.drop_table("lead_note")
    op.drop_column("lead", "retention_review_date")
    op.drop_column("lead", "quote_status")
    op.drop_column("lead", "sample_status")
    op.drop_column("lead", "mock_up_status")
    op.drop_column("lead", "lost_reason")
    op.drop_column("lead", "potential_recurrence")
    op.drop_column("lead", "won_value")
    op.drop_column("lead", "quote_value")
    op.drop_column("lead", "estimated_order_value")
