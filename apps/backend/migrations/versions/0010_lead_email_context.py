"""Add reusable lead contact and email context.

Revision ID: 0010_lead_email_context
Revises: 0009_outreach_drafts
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_lead_email_context"
down_revision: str | None = "0009_outreach_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lead") as batch_op:
        batch_op.add_column(sa.Column("contact_first_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("contact_last_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("contact_role", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("contact_email", sa.String(length=320), nullable=True))
        batch_op.add_column(sa.Column("contact_source_reference", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("personalisation_observation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("relevance_opportunity", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("offer_angle", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("desired_next_step", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("avoid_mentioning", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lead") as batch_op:
        batch_op.drop_column("avoid_mentioning")
        batch_op.drop_column("desired_next_step")
        batch_op.drop_column("offer_angle")
        batch_op.drop_column("relevance_opportunity")
        batch_op.drop_column("personalisation_observation")
        batch_op.drop_column("contact_source_reference")
        batch_op.drop_column("contact_email")
        batch_op.drop_column("contact_role")
        batch_op.drop_column("contact_last_name")
        batch_op.drop_column("contact_first_name")
