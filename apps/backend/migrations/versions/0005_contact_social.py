"""Store canonical contacts and social identities.

Revision ID: 0005_contact_social
Revises: 0004_campaign_automation
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_contact_social"
down_revision: str | None = "0004_campaign_automation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lead") as batch_op:
        batch_op.add_column(sa.Column("phone_number", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("public_email", sa.String(length=320), nullable=True))

    op.create_table(
        "lead_social_identity",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("profile_url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_handle", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("classification", sa.String(length=40), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "profile_url", name="uq_social_identity_profile"),
        sa.UniqueConstraint("platform", "normalized_handle", name="uq_social_identity_handle"),
    )
    op.create_index("ix_social_identity_lead", "lead_social_identity", ["lead_id"])

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, social_profile FROM lead WHERE social_profile IS NOT NULL")
    ).mappings()
    for row in rows:
        url = str(row["social_profile"])
        lowered = url.lower()
        platform = "instagram" if "instagram.com" in lowered else (
            "facebook" if "facebook.com" in lowered or "fb.com" in lowered else "other"
        )
        handle = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1].lower()
        connection.execute(
            sa.text(
                "INSERT OR IGNORE INTO lead_social_identity "
                "(id, lead_id, platform, profile_url, normalized_handle, source_url, "
                "classification, collected_at, created_at) "
                "VALUES (:id, :lead_id, :platform, :profile_url, :handle, :source_url, "
                "'user_observed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": __import__("uuid").uuid4().hex,
                "lead_id": row["id"],
                "platform": platform,
                "profile_url": url,
                "handle": handle,
                "source_url": url,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_social_identity_lead", table_name="lead_social_identity")
    op.drop_table("lead_social_identity")
    with op.batch_alter_table("lead") as batch_op:
        batch_op.drop_column("public_email")
        batch_op.drop_column("phone_number")
