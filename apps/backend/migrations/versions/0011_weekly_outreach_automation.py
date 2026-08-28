"""Add opt-in weekly outreach automation controls.

Revision ID: 0011_weekly_outreach_automation
Revises: 0010_lead_email_context
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_weekly_outreach_automation"
down_revision: str | None = "0010_lead_email_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("campaign") as batch_op:
        batch_op.add_column(
            sa.Column(
                "weekly_outreach_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("weekly_outreach_template_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "weekly_outreach_provider",
                sa.String(length=40),
                nullable=False,
                server_default="scoring",
            )
        )
        batch_op.create_foreign_key(
            "fk_campaign_weekly_outreach_template",
            "message_template",
            ["weekly_outreach_template_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("campaign_run") as batch_op:
        batch_op.add_column(sa.Column("week_start", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("outreach_batch_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_campaign_run_outreach_batch",
            "outreach_batch",
            ["outreach_batch_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_campaign_run_campaign_week", ["campaign_id", "week_start"]
        )
        batch_op.create_index("ix_campaign_run_week", ["week_start"])


def downgrade() -> None:
    with op.batch_alter_table("campaign_run") as batch_op:
        batch_op.drop_index("ix_campaign_run_week")
        batch_op.drop_constraint("uq_campaign_run_campaign_week", type_="unique")
        batch_op.drop_constraint("fk_campaign_run_outreach_batch", type_="foreignkey")
        batch_op.drop_column("outreach_batch_id")
        batch_op.drop_column("week_start")

    with op.batch_alter_table("campaign") as batch_op:
        batch_op.drop_constraint("fk_campaign_weekly_outreach_template", type_="foreignkey")
        batch_op.drop_column("weekly_outreach_provider")
        batch_op.drop_column("weekly_outreach_template_id")
        batch_op.drop_column("weekly_outreach_enabled")
