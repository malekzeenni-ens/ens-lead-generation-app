"""Add durable campaign runs and controlled discovery candidates.

Revision ID: 0004_campaign_automation
Revises: 0003_qualification
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_campaign_automation"
down_revision: str | None = "0003_qualification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("phase", sa.String(length=50), nullable=False),
        sa.Column("provider_status", sa.String(length=40), nullable=False),
        sa.Column("query_summary", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_campaign_run_campaign_created", "campaign_run", ["campaign_id", "created_at"]
    )
    op.create_index("ix_campaign_run_status_created", "campaign_run", ["status", "created_at"])

    op.create_table(
        "discovery_candidate",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("provider_record_id", sa.String(length=300), nullable=False),
        sa.Column("business_name", sa.String(length=300), nullable=False),
        sa.Column("normalized_name", sa.String(length=300), nullable=False),
        sa.Column("location", sa.String(length=500), nullable=False),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("place_types", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("matched_lead_id", sa.String(length=36), nullable=True),
        sa.Column("duplicate_confidence", sa.Float(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_lead_id"], ["lead.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["campaign_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "provider", "provider_record_id", name="uq_candidate_run_provider_record"
        ),
    )
    op.create_index("ix_candidate_run_status", "discovery_candidate", ["run_id", "status"])
    op.create_index(
        "ix_candidate_provider_record", "discovery_candidate", ["provider", "provider_record_id"]
    )
    op.create_index(
        "ix_candidate_normalized_name", "discovery_candidate", ["normalized_name"]
    )

    op.create_table(
        "provider_attempt",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("response_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["campaign_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_attempt_run", "provider_attempt", ["run_id", "started_at"])

    with op.batch_alter_table("score_run") as batch:
        batch.add_column(sa.Column("campaign_run_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("input_fingerprint", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_score_run_campaign_run", "campaign_run", ["campaign_run_id"], ["id"],
            ondelete="SET NULL"
        )
        batch.create_index("ix_score_run_fingerprint", ["lead_id", "campaign_id", "input_fingerprint"])


def downgrade() -> None:
    with op.batch_alter_table("score_run") as batch:
        batch.drop_index("ix_score_run_fingerprint")
        batch.drop_constraint("fk_score_run_campaign_run", type_="foreignkey")
        batch.drop_column("input_fingerprint")
        batch.drop_column("campaign_run_id")
    op.drop_index("ix_provider_attempt_run", table_name="provider_attempt")
    op.drop_table("provider_attempt")
    op.drop_index("ix_candidate_normalized_name", table_name="discovery_candidate")
    op.drop_index("ix_candidate_provider_record", table_name="discovery_candidate")
    op.drop_index("ix_candidate_run_status", table_name="discovery_candidate")
    op.drop_table("discovery_candidate")
    op.drop_index("ix_campaign_run_status_created", table_name="campaign_run")
    op.drop_index("ix_campaign_run_campaign_created", table_name="campaign_run")
    op.drop_table("campaign_run")
