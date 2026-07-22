"""Add curated product families and assign one per campaign.

Revision ID: 0007_product_families
Revises: 0006_message_templates
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_product_families"
down_revision: str | None = "0006_message_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_family",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_product_family_name", "product_family", ["name"])

    with op.batch_alter_table("campaign") as batch_op:
        batch_op.add_column(sa.Column("product_family_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_campaign_product_family",
            "product_family",
            ["product_family_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("campaign") as batch_op:
        batch_op.drop_constraint("fk_campaign_product_family", type_="foreignkey")
        batch_op.drop_column("product_family_id")

    op.drop_index("ix_product_family_name", table_name="product_family")
    op.drop_table("product_family")
