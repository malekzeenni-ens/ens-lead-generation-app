"""Deciding whether a discovered business is a lead we already have (FR-015).

Pure functions, no database. Identifiers are ranked, and the strongest match across all leads
wins, so a phone match on one lead beats a name match on another. A business name is not unique:
it only links automatically when the location agrees, and otherwise goes to operator review.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import IntEnum, StrEnum

from app.domains.leads.identity import normalize_business_name, phone_match_key, website_host

FUZZY_NAME_THRESHOLD = 0.94
_MINIMUM_PHONE_DIGITS = 9
# A full UK postcode; the outward code (first half) identifies the district.
_POSTCODE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*\d[A-Z]{2}\b", re.IGNORECASE)
_LOCATION_STOP_WORDS = frozenset(
    {
        "uk",
        "gb",
        "united",
        "kingdom",
        "great",
        "britain",
        "england",
        "scotland",
        "wales",
        "northern",
        "ireland",
    }
)


class MatchRank(IntEnum):
    """Lower is stronger."""

    SOCIAL = 1
    WEBSITE = 2
    PHONE = 3
    EMAIL = 4
    NAME_AND_LOCALITY = 5
    NAME_ONLY = 6
    FUZZY_NAME = 7


class MatchKind(StrEnum):
    EXACT = "exact"
    REVIEW = "review"
    NONE = "none"


_EXACT_REASONS = {
    MatchRank.SOCIAL: "Same social profile",
    MatchRank.WEBSITE: "Same website",
    MatchRank.PHONE: "Same phone number",
    MatchRank.EMAIL: "Same email address",
    MatchRank.NAME_AND_LOCALITY: "Same name and location",
}
NAME_ONLY_REVIEW_REASON = (
    "Same name as an existing lead in a different or unknown location. Link it only if it is "
    "the same business."
)


@dataclass(frozen=True)
class Locality:
    outward_code: str | None
    tokens: frozenset[str]

    @property
    def known(self) -> bool:
        return self.outward_code is not None or bool(self.tokens)


def locality(location: str | None) -> Locality:
    text = location or ""
    postcode = _POSTCODE.search(text)
    outward = postcode.group(1).upper() if postcode else None
    if postcode:
        text = text[: postcode.start()] + " " + text[postcode.end() :]
    tokens = frozenset(
        word
        for word in re.findall(r"[a-z0-9]+", text.casefold())
        if not any(character.isdigit() for character in word)
        and len(word) > 1
        and word not in _LOCATION_STOP_WORDS
    )
    return Locality(outward_code=outward, tokens=tokens)


def same_locality(first: Locality, second: Locality) -> bool:
    """Equal postcode districts when both have one; otherwise every place word of the shorter
    location appears in the longer ("Leeds" and "12 High Street, Leeds")."""
    if first.outward_code and second.outward_code:
        return first.outward_code == second.outward_code
    if not first.tokens or not second.tokens:
        return False
    shorter, longer = sorted((first.tokens, second.tokens), key=len)
    return shorter <= longer


@dataclass(frozen=True)
class MatchKeys:
    normalized_name: str
    locality: Locality
    website_host: str | None = None
    phone_key: str | None = None
    emails: frozenset[str] = field(default_factory=frozenset)
    social: frozenset[tuple[str, str]] = field(default_factory=frozenset)


def match_keys(
    *,
    business_name: str,
    location: str | None,
    website: str | None = None,
    phone: str | None = None,
    emails: Iterable[str | None] = (),
    social: Iterable[tuple[str, str]] = (),
) -> MatchKeys:
    phone_key = phone_match_key(phone)
    return MatchKeys(
        normalized_name=normalize_business_name(business_name),
        locality=locality(location),
        website_host=website_host(website),
        phone_key=phone_key if phone_key and len(phone_key) >= _MINIMUM_PHONE_DIGITS else None,
        emails=frozenset(email.strip().casefold() for email in emails if email and "@" in email),
        social=frozenset((platform, handle) for platform, handle in social if handle),
    )


@dataclass(frozen=True)
class MatchResult:
    kind: MatchKind
    lead_id: str | None = None
    rank: MatchRank | None = None
    confidence: float | None = None
    reason: str | None = None


NO_MATCH = MatchResult(kind=MatchKind.NONE)


def _identifier_rank(candidate: MatchKeys, lead: MatchKeys) -> MatchRank | None:
    if candidate.social & lead.social:
        return MatchRank.SOCIAL
    if candidate.website_host and candidate.website_host == lead.website_host:
        return MatchRank.WEBSITE
    if candidate.phone_key and candidate.phone_key == lead.phone_key:
        return MatchRank.PHONE
    if candidate.emails & lead.emails:
        return MatchRank.EMAIL
    if candidate.normalized_name and candidate.normalized_name == lead.normalized_name:
        if same_locality(candidate.locality, lead.locality):
            return MatchRank.NAME_AND_LOCALITY
        return MatchRank.NAME_ONLY
    return None


def match(candidate: MatchKeys, leads: Iterable[tuple[str, MatchKeys]]) -> MatchResult:
    """The strongest match across `leads`, which the caller orders newest first so a tie goes
    to the most recently created lead."""
    lead_list = list(leads)
    best: tuple[MatchRank, str] | None = None
    for lead_id, keys in lead_list:
        rank = _identifier_rank(candidate, keys)
        if rank is not None and (best is None or rank < best[0]):
            best = (rank, lead_id)
            if rank is MatchRank.SOCIAL:
                break
    if best is not None:
        rank, lead_id = best
        if rank is MatchRank.NAME_ONLY:
            return MatchResult(
                kind=MatchKind.REVIEW,
                lead_id=lead_id,
                rank=rank,
                confidence=1.0,
                reason=NAME_ONLY_REVIEW_REASON,
            )
        return MatchResult(
            kind=MatchKind.EXACT, lead_id=lead_id, rank=rank, reason=_EXACT_REASONS[rank]
        )

    fuzzy: tuple[float, str] | None = None
    for lead_id, keys in lead_list:
        if not candidate.normalized_name or not keys.normalized_name:
            continue
        ratio = SequenceMatcher(None, candidate.normalized_name, keys.normalized_name).ratio()
        if ratio >= FUZZY_NAME_THRESHOLD and (fuzzy is None or ratio > fuzzy[0]):
            fuzzy = (ratio, lead_id)
    if fuzzy is not None:
        return MatchResult(
            kind=MatchKind.REVIEW,
            lead_id=fuzzy[1],
            rank=MatchRank.FUZZY_NAME,
            confidence=round(fuzzy[0], 3),
        )
    return NO_MATCH
