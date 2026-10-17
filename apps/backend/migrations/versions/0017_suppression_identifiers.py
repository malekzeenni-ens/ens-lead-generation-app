"""Store every suppressed identifier, and why a discovery candidate needs review.

A suppression used to hold only a hash of name and location, so a deleted suppressed business came
back when a provider reported it under a differently formatted address. Each active or lifted
suppression now gets one row per identifier (ADR-023). Records whose lead still exists are
backfilled from it; records whose lead was already deleted keep only the name/location hash they
always had.

The hashing below is a frozen copy of `app.domains.leads.suppression` as of this revision, so a
later change to the application cannot alter what this migration wrote.

Revision ID: 0017_suppression_identifiers
Revises: 0016_seed_outreach_templates
Create Date: 2026-10-18
"""

import hashlib
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import sqlalchemy as sa
from alembic import op

revision: str = "0017_suppression_identifiers"
down_revision: str | None = "0016_seed_outreach_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOCIAL_HOSTS = {
    "instagram": {"instagram.com", "www.instagram.com"},
    "facebook": {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.com", "www.fb.com"},
}


def _normalize_name(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip().split())


def _hash(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}|{value}".encode()).hexdigest()


def _social_key(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").casefold()
    platform = next((name for name, hosts in _SOCIAL_HOSTS.items() if host in hosts), None)
    if platform is None:
        return None
    if platform == "facebook" and parsed.path.casefold().rstrip("/") == "/profile.php":
        handle = (parse_qs(parsed.query).get("id") or [""])[0]
    else:
        handle = next((part for part in parsed.path.split("/") if part), "")
    handle = handle.removeprefix("@").casefold()[:200]
    if handle in {"", "accounts", "explore", "p", "reel", "reels", "stories", "share", "groups"}:
        return None
    return platform, handle


def _lead_hashes(
    lead: sa.Row[tuple[object, ...]], social_keys: set[tuple[str, str]]
) -> set[tuple[str, str]]:
    hashes: set[tuple[str, str]] = set()
    name = _normalize_name(str(lead.business_name))
    if name:
        hashes.add(("name", _hash("name", name)))
    host = (urlparse(str(lead.website or "")).hostname or "").casefold().removeprefix("www.")
    if host:
        hashes.add(("website_host", _hash("website_host", host)))
    digits = "".join(character for character in str(lead.phone_number or "") if character.isdigit())
    phone_key = digits[-10:] if len(digits) >= 10 else digits
    if len(phone_key) >= 9:
        hashes.add(("phone", _hash("phone", phone_key)))
    for email in (lead.public_email, lead.contact_email):
        normalised = str(email or "").strip().casefold()
        if "@" in normalised:
            hashes.add(("email", _hash("email", normalised)))
    profile_key = _social_key(str(lead.social_profile) if lead.social_profile else None)
    for platform, handle in social_keys | ({profile_key} if profile_key else set()):
        if platform in _SOCIAL_HOSTS and handle:
            hashes.add(("social", _hash("social", f"{platform}:{handle}")))
    return hashes


def upgrade() -> None:
    op.create_table(
        "suppression_identifier",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "suppression_id",
            sa.String(length=36),
            sa.ForeignKey("suppression_record.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("value_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "suppression_id", "kind", "value_hash", name="uq_suppression_identifier_value"
        ),
    )
    op.create_index(
        "ix_suppression_identifier_lookup", "suppression_identifier", ["kind", "value_hash"]
    )
    with op.batch_alter_table("discovery_candidate") as batch:
        batch.add_column(sa.Column("review_reason", sa.Text(), nullable=True))

    connection = op.get_bind()
    records = connection.execute(
        sa.text("SELECT id, lead_id, identifier_hash FROM suppression_record")
    ).all()
    now = datetime.now(UTC)
    rows: list[dict[str, object]] = []
    for record in records:
        hashes = {("name_location", str(record.identifier_hash))}
        if record.lead_id is not None:
            lead = connection.execute(
                sa.text(
                    "SELECT business_name, website, phone_number, public_email, contact_email, "
                    "social_profile FROM lead WHERE id = :lead_id"
                ),
                {"lead_id": record.lead_id},
            ).first()
            if lead is not None:
                social_keys = {
                    (str(platform), str(handle))
                    for platform, handle in connection.execute(
                        sa.text(
                            "SELECT platform, normalized_handle FROM lead_social_identity "
                            "WHERE lead_id = :lead_id"
                        ),
                        {"lead_id": record.lead_id},
                    )
                }
                hashes |= _lead_hashes(lead, social_keys)
        rows.extend(
            {
                "id": str(uuid.uuid4()),
                "suppression_id": record.id,
                "kind": kind,
                "value_hash": value,
                "created_at": now,
            }
            for kind, value in sorted(hashes)
        )
    if rows:
        identifier_table = sa.table(
            "suppression_identifier",
            sa.column("id", sa.String),
            sa.column("suppression_id", sa.String),
            sa.column("kind", sa.String),
            sa.column("value_hash", sa.String),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(identifier_table, rows)


def downgrade() -> None:
    with op.batch_alter_table("discovery_candidate") as batch:
        batch.drop_column("review_reason")
    op.drop_index("ix_suppression_identifier_lookup", table_name="suppression_identifier")
    op.drop_table("suppression_identifier")
