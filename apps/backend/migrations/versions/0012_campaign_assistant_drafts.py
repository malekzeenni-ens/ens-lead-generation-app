"""Add local campaign assistant drafts, revisions and confirmed overrides.

Revision ID: 0012_campaign_assistant_drafts
Revises: 0011_weekly_outreach_automation
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_campaign_assistant_drafts"
down_revision: str | None = "0011_weekly_outreach_automation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_draft",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("original_request", sa.Text(), nullable=False),
        sa.Column("current_payload", sa.JSON(), nullable=True),
        sa.Column("assistant_message", sa.Text(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_digest", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("resource_profile", sa.String(length=40), nullable=False),
        sa.Column("generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_token_count", sa.Integer(), nullable=True),
        sa.Column("output_token_count", sa.Integer(), nullable=True),
        sa.Column("approved_campaign_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('generating', 'awaiting_input', 'awaiting_override_confirmation', "
            "'ready', 'generation_failed', 'approved', 'discarded')",
            name="ck_campaign_draft_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_campaign_draft_version_positive"),
        sa.ForeignKeyConstraint(["approved_campaign_id"], ["campaign.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approved_campaign_id"),
    )
    op.create_index("ix_campaign_draft_status_updated", "campaign_draft", ["status", "updated_at"])

    op.create_table(
        "campaign_draft_revision",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revision_source", sa.String(length=40), nullable=False),
        sa.Column("user_instruction", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("assistant_message", sa.Text(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("resource_profile", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["campaign_draft.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", "version", name="uq_campaign_draft_revision_version"),
    )
    op.create_index(
        "ix_campaign_draft_revision_created",
        "campaign_draft_revision",
        ["draft_id", "created_at"],
    )

    op.create_table(
        "campaign_draft_override",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("originating_message", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("playbook_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'partially_confirmed', 'rejected', 'superseded')",
            name="ck_campaign_draft_override_status",
        ),
        sa.ForeignKeyConstraint(["draft_id"], ["campaign_draft.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_campaign_draft_override_status",
        "campaign_draft_override",
        ["draft_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_draft_override_status", table_name="campaign_draft_override")
    op.drop_table("campaign_draft_override")
    op.drop_index("ix_campaign_draft_revision_created", table_name="campaign_draft_revision")
    op.drop_table("campaign_draft_revision")
    op.drop_index("ix_campaign_draft_status_updated", table_name="campaign_draft")
    op.drop_table("campaign_draft")
