"""Add local outreach draft review and approval workflow.

Revision ID: 0009_outreach_drafts
Revises: 0008_template_product_families
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_outreach_drafts"
down_revision: str | None = "0008_template_product_families"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lead") as batch_op:
        batch_op.add_column(sa.Column("outreach_hold_until", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("outreach_hold_reason", sa.Text(), nullable=True))

    op.create_table(
        "outreach_batch",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=True),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["message_template.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outreach_batch_campaign_created",
        "outreach_batch",
        ["campaign_id", "created_at"],
    )
    op.create_index(
        "ix_outreach_batch_status_created", "outreach_batch", ["status", "created_at"]
    )

    op.create_table(
        "outreach_draft",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("sync_status", sa.String(length=30), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("approved_version", sa.Integer(), nullable=True),
        sa.Column("approved_content_hash", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["outreach_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["message_template.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outreach_draft_batch_review", "outreach_draft", ["batch_id", "review_status"]
    )
    op.create_index(
        "ix_outreach_draft_lead_created", "outreach_draft", ["lead_id", "created_at"]
    )

    op.create_table(
        "outreach_draft_revision",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("editor", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["outreach_draft.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_id", "version", name="uq_outreach_draft_revision_version"
        ),
    )
    op.create_index(
        "ix_outreach_revision_draft_created",
        "outreach_draft_revision",
        ["draft_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outreach_revision_draft_created", table_name="outreach_draft_revision"
    )
    op.drop_table("outreach_draft_revision")
    op.drop_index("ix_outreach_draft_lead_created", table_name="outreach_draft")
    op.drop_index("ix_outreach_draft_batch_review", table_name="outreach_draft")
    op.drop_table("outreach_draft")
    op.drop_index("ix_outreach_batch_status_created", table_name="outreach_batch")
    op.drop_index("ix_outreach_batch_campaign_created", table_name="outreach_batch")
    op.drop_table("outreach_batch")
    with op.batch_alter_table("lead") as batch_op:
        batch_op.drop_column("outreach_hold_reason")
        batch_op.drop_column("outreach_hold_until")
