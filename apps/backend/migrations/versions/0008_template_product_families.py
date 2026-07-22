"""Link message templates to curated product families.

Revision ID: 0008_template_product_families
Revises: 0007_product_families
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_template_product_families"
down_revision: str | None = "0007_product_families"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("message_template") as batch_op:
        batch_op.add_column(
            sa.Column("product_family_ids", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("message_template") as batch_op:
        batch_op.drop_column("product_family_ids")
