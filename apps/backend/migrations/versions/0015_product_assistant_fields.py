"""Add product sales knowledge, knowledge notes, proven fits and draft edit ratio.

Revision ID: 0015_product_assistant_fields
Revises: 0014_backup_manifest_assistant_files
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_product_assistant_fields"
down_revision: str | None = "0014_backup_manifest_assistant_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("product") as batch_op:
        batch_op.add_column(sa.Column("summary", sa.String(length=400)))
        batch_op.add_column(
            sa.Column("materials", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("occasions", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(sa.Column("product_url", sa.String(length=2048)))
        batch_op.add_column(
            sa.Column("b2b_relevant", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("bulk_ready", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("b2b_notes", sa.Text()))
        batch_op.add_column(sa.Column("custom_options", sa.String(length=300)))
        batch_op.add_column(
            sa.Column("attributes", sa.JSON(), nullable=False, server_default="{}")
        )
        batch_op.add_column(
            sa.Column(
                "enrichment_source",
                sa.String(length=20),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(sa.Column("source_hash", sa.String(length=32)))
        batch_op.add_column(sa.Column("enriched_hash", sa.String(length=32)))
        batch_op.add_column(sa.Column("last_seen_import_at", sa.DateTime(timezone=True)))

    op.create_index("ix_product_b2b_relevant", "product", ["b2b_relevant"])
    op.create_index("ix_product_enrichment_source", "product", ["enrichment_source"])

    op.create_table(
        "knowledge_note",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("product_family_id", sa.String(length=36), nullable=True),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("product_handles", sa.JSON(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("manual", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_family_id"], ["product_family.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_note_title", "knowledge_note", ["title"])

    op.create_table(
        "proven_fit",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("segment", sa.String(length=120), nullable=False),
        sa.Column("product_handles", sa.JSON(), nullable=False),
        sa.Column("use", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=400), nullable=False),
        sa.Column("client_label", sa.String(length=200), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=True),
        sa.Column("share_client_name", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('confirmed_from_website', 'please_confirm', 'confirmed')",
            name="ck_proven_fit_status",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_proven_fit_segment", "proven_fit", ["segment"])

    with op.batch_alter_table("outreach_draft_revision") as batch_op:
        batch_op.add_column(sa.Column("edit_distance_ratio", sa.Float()))


def downgrade() -> None:
    with op.batch_alter_table("outreach_draft_revision") as batch_op:
        batch_op.drop_column("edit_distance_ratio")

    op.drop_index("ix_proven_fit_segment", table_name="proven_fit")
    op.drop_table("proven_fit")
    op.drop_index("ix_knowledge_note_title", table_name="knowledge_note")
    op.drop_table("knowledge_note")

    op.drop_index("ix_product_enrichment_source", table_name="product")
    op.drop_index("ix_product_b2b_relevant", table_name="product")
    with op.batch_alter_table("product") as batch_op:
        for column in (
            "last_seen_import_at",
            "enriched_hash",
            "source_hash",
            "enrichment_source",
            "attributes",
            "custom_options",
            "b2b_notes",
            "bulk_ready",
            "b2b_relevant",
            "product_url",
            "occasions",
            "materials",
            "summary",
        ):
            batch_op.drop_column(column)
