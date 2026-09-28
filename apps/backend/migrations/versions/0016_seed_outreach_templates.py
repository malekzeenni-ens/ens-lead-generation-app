"""Seed the three B2B outreach templates.

Created only where the topic does not already exist, so an operator who has renamed, edited or
deleted one does not get it back. Every token used here is already supported by
`OutreachService._template_values`.

Revision ID: 0016_seed_outreach_templates
Revises: 0015_product_assistant_fields
Create Date: 2026-09-28
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0016_seed_outreach_templates"
down_revision: str | None = "0015_product_assistant_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FIRST_CONTACT_BODY = """Hi {{greeting_name}},

{{personalisation_observation}}

I run Etch 'N' Shine, a small laser engraving studio. {{offer_angle}} A few pieces that tend to \
suit businesses like yours:
{{products}}

{{desired_next_step}} I can send a digital mock-up with your logo first, so you can see it before \
committing to anything.

Kind regards,
Malek
Etch 'N' Shine | etchnshine.com | info@etchnshine.com

If this isn't relevant, just reply "no thanks" and I won't get in touch again."""

_FOLLOW_UP_BODY = """Hi {{greeting_name}},

A quick follow-up with one idea. {{relevance_opportunity}}

Happy to put a mock-up together with your logo, with no obligation.

Malek
Etch 'N' Shine | etchnshine.com"""

_REPLY_BODY = """Hi {{greeting_name}},

Thanks for getting back to me. {{offer_angle}}

I'll put a quote together once I know quantities and whether you'd like your logo, names or \
both. {{desired_next_step}}

Kind regards,
Malek
Etch 'N' Shine | etchnshine.com | info@etchnshine.com"""

_TEMPLATES = (
    (
        "First contact - local business",
        "Engraved pieces for {{business_name}}",
        _FIRST_CONTACT_BODY,
    ),
    (
        "Follow-up one",
        "Re: Engraved pieces for {{business_name}}",
        _FOLLOW_UP_BODY,
    ),
    (
        "Reply to an enquiry",
        "Your engraving enquiry - {{business_name}}",
        _REPLY_BODY,
    ),
)


# A typed table so the dialect converts the timestamps and JSON column itself. Passing a raw
# datetime through `sa.text` would go via sqlite3's deprecated datetime adapter.
_message_template = sa.table(
    "message_template",
    sa.column("id", sa.String),
    sa.column("topic", sa.String),
    sa.column("subject", sa.String),
    sa.column("body", sa.Text),
    sa.column("product_family_ids", sa.JSON),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.now(UTC)
    for topic, subject, body in _TEMPLATES:
        exists = connection.execute(
            sa.text("SELECT 1 FROM message_template WHERE topic = :topic LIMIT 1"),
            {"topic": topic},
        ).first()
        if exists is not None:
            continue
        connection.execute(
            _message_template.insert().values(
                id=str(uuid.uuid4()),
                topic=topic,
                subject=subject,
                body=body,
                product_family_ids=[],
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    for topic, _subject, _body in _TEMPLATES:
        connection.execute(
            sa.text("DELETE FROM message_template WHERE topic = :topic"),
            {"topic": topic},
        )
