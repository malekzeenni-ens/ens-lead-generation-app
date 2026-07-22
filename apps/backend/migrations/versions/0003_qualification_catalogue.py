"""Add product catalogue, deterministic scoring and weekly shortlists.

Revision ID: 0003_qualification
Revises: 0002_local_crm
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_qualification"
down_revision: str | None = "0002_local_crm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lead", sa.Column("current_score", sa.Integer(), nullable=True))
    op.add_column("lead", sa.Column("score_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "product",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shopify_handle", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_segments", sa.JSON(), nullable=False),
        sa.Column("example_use_cases", sa.JSON(), nullable=False),
        sa.Column("image_reference", sa.String(length=2048), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("pricing_guidance", sa.String(length=200), nullable=True),
        sa.Column("sample_eligible", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("variant_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shopify_handle"),
    )
    op.create_index("ix_product_active_category", "product", ["active", "category"])
    op.create_index("ix_product_name", "product", ["name"])

    op.create_table(
        "scoring_profile",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("segment", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("segment", "version", name="uq_scoring_profile_segment_version"),
    )
    op.create_index(
        "ix_scoring_profile_segment_active", "scoring_profile", ["segment", "active"]
    )

    op.create_table(
        "score_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("rule_version", sa.String(length=100), nullable=False),
        sa.Column("calculated_score", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Integer(), nullable=False),
        sa.Column("manual_override", sa.Boolean(), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("product_matches", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["scoring_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_score_run_lead_time", "score_run", ["lead_id", "created_at"])
    op.create_index(
        "ix_score_run_campaign_score", "score_run", ["campaign_id", "final_score"]
    )

    op.create_table(
        "shortlist",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "week_start", name="uq_shortlist_campaign_week"),
    )
    op.create_index("ix_shortlist_week", "shortlist", ["week_start"])

    op.create_table(
        "shortlist_item",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shortlist_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("score_run_id", sa.String(length=36), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("product_matches", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["score_run_id"], ["score_run.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shortlist_id"], ["shortlist.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shortlist_id", "lead_id", name="uq_shortlist_item_lead"),
    )
    op.create_index(
        "ix_shortlist_item_decision", "shortlist_item", ["shortlist_id", "decision"]
    )


def downgrade() -> None:
    op.drop_index("ix_shortlist_item_decision", table_name="shortlist_item")
    op.drop_table("shortlist_item")
    op.drop_index("ix_shortlist_week", table_name="shortlist")
    op.drop_table("shortlist")
    op.drop_index("ix_score_run_campaign_score", table_name="score_run")
    op.drop_index("ix_score_run_lead_time", table_name="score_run")
    op.drop_table("score_run")
    op.drop_index("ix_scoring_profile_segment_active", table_name="scoring_profile")
    op.drop_table("scoring_profile")
    op.drop_index("ix_product_name", table_name="product")
    op.drop_index("ix_product_active_category", table_name="product")
    op.drop_table("product")
    op.drop_column("lead", "score_updated_at")
    op.drop_column("lead", "current_score")
