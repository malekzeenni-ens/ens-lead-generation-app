"""Store reusable outreach message templates.

Revision ID: 0006_message_templates
Revises: 0005_contact_social
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_message_templates"
down_revision: str | None = "0005_contact_social"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_template",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_template_topic", "message_template", ["topic"])


def downgrade() -> None:
    op.drop_index("ix_message_template_topic", table_name="message_template")
    op.drop_table("message_template")
