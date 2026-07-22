"""Initial local operating core.

Revision ID: 0001_local_core
Revises: None
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_local_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("segment", sa.String(length=100), nullable=False),
        sa.Column("primary_location", sa.String(length=200), nullable=False),
        sa.Column("radius_miles", sa.Float(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("exclusion_keywords", sa.JSON(), nullable=False),
        sa.Column("product_categories", sa.JSON(), nullable=False),
        sa.Column("discovery_sources", sa.JSON(), nullable=False),
        sa.Column("weekly_shortlist_size", sa.Integer(), nullable=False),
        sa.Column("minimum_score_threshold", sa.Integer(), nullable=False),
        sa.Column("preferred_channels", sa.JSON(), nullable=False),
        sa.Column("offer_settings", sa.JSON(), nullable=False),
        sa.Column("discovery_mode", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("minimum_score_threshold BETWEEN 0 AND 100", name="ck_campaign_score_threshold"),
        sa.CheckConstraint("radius_miles > 0", name="ck_campaign_radius_positive"),
        sa.CheckConstraint("weekly_shortlist_size BETWEEN 1 AND 50", name="ck_campaign_shortlist_size"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_campaign_status_segment", "campaign", ["status", "segment"])

    op.create_table(
        "lead",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("segment", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("social_profile", sa.String(length=2048), nullable=True),
        sa.Column("contact_classification", sa.String(length=50), nullable=False),
        sa.Column("pipeline_stage", sa.String(length=50), nullable=False),
        sa.Column("suppressed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_normalized_name", "lead", ["normalized_name"])
    op.create_index("ix_lead_segment_stage", "lead", ["segment", "pipeline_stage"])
    op.create_index("ix_lead_suppressed", "lead", ["suppressed"])

    op.create_table(
        "source_system",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_source_system_type", "source_system", ["source_type"])

    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_created_at", "audit_event", ["created_at"])
    op.create_index("ix_audit_entity", "audit_event", ["entity_type", "entity_id"])

    op.create_table(
        "backup_manifest",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("backup_filename", sa.String(length=255), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("integrity_result", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("application_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_created_at", "backup_manifest", ["created_at"])

    op.create_table(
        "lead_campaign",
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("lead_id", "campaign_id"),
    )

    op.create_table(
        "lead_stage_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("previous_stage", sa.String(length=50), nullable=True),
        sa.Column("new_stage", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stage_event_lead_time", "lead_stage_event", ["lead_id", "created_at"])

    op.create_table(
        "source_observation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("source_system_id", sa.String(length=36), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("observed_value", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("collection_method", sa.String(length=50), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_system_id"], ["source_system.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_observation_collected_at", "source_observation", ["collected_at"])
    op.create_index(
        "ix_observation_lead_source", "source_observation", ["lead_id", "source_system_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_observation_lead_source", table_name="source_observation")
    op.drop_index("ix_observation_collected_at", table_name="source_observation")
    op.drop_table("source_observation")
    op.drop_index("ix_stage_event_lead_time", table_name="lead_stage_event")
    op.drop_table("lead_stage_event")
    op.drop_table("lead_campaign")
    op.drop_index("ix_backup_created_at", table_name="backup_manifest")
    op.drop_table("backup_manifest")
    op.drop_index("ix_audit_entity", table_name="audit_event")
    op.drop_index("ix_audit_created_at", table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_index("ix_source_system_type", table_name="source_system")
    op.drop_table("source_system")
    op.drop_index("ix_lead_suppressed", table_name="lead")
    op.drop_index("ix_lead_segment_stage", table_name="lead")
    op.drop_index("ix_lead_normalized_name", table_name="lead")
    op.drop_table("lead")
    op.drop_index("ix_campaign_status_segment", table_name="campaign")
    op.drop_table("campaign")

