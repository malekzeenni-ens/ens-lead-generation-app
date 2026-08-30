"""Add assistant file archive metadata to backup manifests.

Revision ID: 0014_backup_manifest_assistant_files
Revises: 0013_general_assistant
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_backup_manifest_assistant_files"
down_revision: str | None = "0013_general_assistant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("backup_manifest") as batch_op:
        batch_op.add_column(sa.Column("assistant_files_archive", sa.String(length=255)))
        batch_op.add_column(sa.Column("assistant_files_checksum_sha256", sa.String(length=64)))
        batch_op.add_column(
            sa.Column(
                "assistant_files_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("backup_manifest") as batch_op:
        batch_op.drop_column("assistant_files_count")
        batch_op.drop_column("assistant_files_checksum_sha256")
        batch_op.drop_column("assistant_files_archive")
