"""Suppression identifiers (ADR-023).

A suppression stores a minimised SHA-256 of every identifier that could bring the business back:
its name with location, its name alone, website host, phone numbers, email addresses and
Instagram/Facebook handles. They outlive privacy deletion of the lead, so a provider that finds
the business again under a differently formatted address is still recognised.

Every identifier except the bare name blocks a lead outright. Names are not unique, so a
discovery candidate that matches a suppression only by name goes to operator review instead.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import Lead, LeadSocialIdentity, SuppressionIdentifier, SuppressionRecord
from app.domains.leads.identity import (
    lead_identifier_hash,
    normalize_business_name,
    phone_match_key,
    social_identity,
    website_host,
)

logger = logging.getLogger(__name__)

# Shorter digit strings are too likely to be fragments or extensions to identify a business.
_MINIMUM_PHONE_DIGITS = 9
_SOCIAL_PLATFORMS = frozenset({"instagram", "facebook"})


class IdentifierKind(StrEnum):
    NAME_LOCATION = "name_location"
    NAME = "name"
    WEBSITE_HOST = "website_host"
    PHONE = "phone"
    EMAIL = "email"
    SOCIAL = "social"


# Strongest first; when several identifiers match, the message names the strongest.
_STRONG_PRIORITY: tuple[IdentifierKind, ...] = (
    IdentifierKind.SOCIAL,
    IdentifierKind.WEBSITE_HOST,
    IdentifierKind.PHONE,
    IdentifierKind.EMAIL,
    IdentifierKind.NAME_LOCATION,
)
STRONG_KINDS = frozenset(_STRONG_PRIORITY)

_LABELS = {
    IdentifierKind.NAME_LOCATION: "business name and location",
    IdentifierKind.NAME: "business name",
    IdentifierKind.WEBSITE_HOST: "website",
    IdentifierKind.PHONE: "phone number",
    IdentifierKind.EMAIL: "email address",
    IdentifierKind.SOCIAL: "social profile",
}

IdentifierHash = tuple[IdentifierKind, str]


def _hash(kind: IdentifierKind, value: str) -> str:
    return hashlib.sha256(f"{kind.value}|{value}".encode()).hexdigest()


def identifier_hashes(
    *,
    business_name: str,
    location: str,
    website: str | None = None,
    phones: Iterable[str | None] = (),
    emails: Iterable[str | None] = (),
    social_keys: Iterable[tuple[str, str]] = (),
) -> set[IdentifierHash]:
    """Hashes of every identifier present. The name/location hash keeps its original format so
    records written before ADR-023 still match."""
    hashes: set[IdentifierHash] = {
        (IdentifierKind.NAME_LOCATION, lead_identifier_hash(business_name, location))
    }
    name = normalize_business_name(business_name)
    if name:
        hashes.add((IdentifierKind.NAME, _hash(IdentifierKind.NAME, name)))
    host = website_host(website)
    if host:
        hashes.add((IdentifierKind.WEBSITE_HOST, _hash(IdentifierKind.WEBSITE_HOST, host)))
    for phone in phones:
        key = phone_match_key(phone)
        if key and len(key) >= _MINIMUM_PHONE_DIGITS:
            hashes.add((IdentifierKind.PHONE, _hash(IdentifierKind.PHONE, key)))
    for email in emails:
        normalised = (email or "").strip().casefold()
        if "@" in normalised:
            hashes.add((IdentifierKind.EMAIL, _hash(IdentifierKind.EMAIL, normalised)))
    for platform, handle in social_keys:
        if platform in _SOCIAL_PLATFORMS and handle:
            hashes.add(
                (IdentifierKind.SOCIAL, _hash(IdentifierKind.SOCIAL, f"{platform}:{handle}"))
            )
    return hashes


def social_keys_from_urls(urls: Iterable[str | None]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for url in urls:
        if not url:
            continue
        try:
            platform, handle, _ = social_identity(str(url))
        except ValueError:
            continue
        keys.add((platform, handle))
    return keys


def lead_identifier_hashes(session: Session, lead: Lead) -> set[IdentifierHash]:
    """Every identifier the lead currently carries, including social identities added in this
    transaction (the caller flushes first; they are read from the database, not the possibly
    stale relationship collection)."""
    stored_social = {
        (platform, handle)
        for platform, handle in session.execute(
            select(LeadSocialIdentity.platform, LeadSocialIdentity.normalized_handle).where(
                LeadSocialIdentity.lead_id == lead.id
            )
        )
    }
    return identifier_hashes(
        business_name=lead.business_name,
        location=lead.location,
        website=lead.website,
        phones=[lead.phone_number],
        emails=[lead.public_email, lead.contact_email],
        social_keys=stored_social | social_keys_from_urls([lead.social_profile]),
    )


@dataclass(frozen=True)
class SuppressionMatch:
    record: SuppressionRecord
    kind: IdentifierKind

    @property
    def strong(self) -> bool:
        return self.kind in STRONG_KINDS

    @property
    def label(self) -> str:
        return _LABELS[self.kind]


def find_active_suppression(
    session: Session,
    hashes: Iterable[IdentifierHash],
    *,
    exclude_lead_id: str | None = None,
    include_name_only: bool = False,
) -> SuppressionMatch | None:
    """The strongest active suppression matching any of `hashes`, or None.

    `exclude_lead_id` skips suppressions of that lead, so editing a suppressed lead is not
    blocked by its own record. A bare name match is returned only with `include_name_only`.
    """
    wanted = [
        (kind, value)
        for kind, value in set(hashes)
        if kind in STRONG_KINDS or (include_name_only and kind is IdentifierKind.NAME)
    ]
    if not wanted:
        return None
    rows = session.execute(
        select(SuppressionIdentifier.kind, SuppressionRecord)
        .join(SuppressionIdentifier.suppression)
        .where(
            SuppressionRecord.active.is_(True),
            or_(
                *(
                    and_(
                        SuppressionIdentifier.kind == kind.value,
                        SuppressionIdentifier.value_hash == value,
                    )
                    for kind, value in wanted
                )
            ),
        )
        .order_by(SuppressionRecord.effective_at.desc())
    ).all()
    matches = [
        SuppressionMatch(record=record, kind=IdentifierKind(kind))
        for kind, record in rows
        if exclude_lead_id is None or record.lead_id != exclude_lead_id
    ]
    if not matches:
        return None
    for kind in (*_STRONG_PRIORITY, IdentifierKind.NAME):
        for match in matches:
            if match.kind is kind:
                return match
    return None


def record_identifiers(
    record: SuppressionRecord, hashes: Iterable[IdentifierHash]
) -> list[IdentifierKind]:
    """Attach any identifiers the record does not already hold; returns the kinds added."""
    existing = {(identifier.kind, identifier.value_hash) for identifier in record.identifiers}
    added: list[IdentifierKind] = []
    for kind, value in sorted(set(hashes)):
        if (kind.value, value) in existing:
            continue
        record.identifiers.append(SuppressionIdentifier(kind=kind.value, value_hash=value))
        added.append(kind)
    if added:
        logger.info(
            "Suppression identifiers recorded",
            extra={
                "suppression_id": record.id,
                "identifier_kinds": sorted({kind.value for kind in added}),
                "identifier_count": len(added),
            },
        )
    return added
