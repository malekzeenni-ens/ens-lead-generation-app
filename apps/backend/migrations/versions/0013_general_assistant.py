"""Add general local assistant conversations and attachments.

Revision ID: 0013_general_assistant
Revises: 0012_campaign_assistant_drafts
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_general_assistant"
down_revision: str | None = "0012_campaign_assistant_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_conversation_updated", "assistant_conversation", ["updated_at"])

    op.create_table(
        "assistant_message",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("resource_profile", sa.String(length=40), nullable=True),
        sa.Column("generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("campaign_draft_suggested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_assistant_message_role"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["assistant_conversation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assistant_message_conversation_created",
        "assistant_message",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "assistant_attachment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_name", sa.String(length=100), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IN ('uploaded', 'generated')",
            name="ck_assistant_attachment_direction",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["assistant_conversation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["message_id"], ["assistant_message.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_name"),
    )
    op.create_index(
        "ix_assistant_attachment_conversation",
        "assistant_attachment",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_attachment_conversation", table_name="assistant_attachment")
    op.drop_table("assistant_attachment")
    op.drop_index("ix_assistant_message_conversation_created", table_name="assistant_message")
    op.drop_table("assistant_message")
    op.drop_index("ix_assistant_conversation_updated", table_name="assistant_conversation")
    op.drop_table("assistant_conversation")
