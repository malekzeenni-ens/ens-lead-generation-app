"""Turning a Shopify export into something the assistant can sell from.

A Shopify CSV says what a product *is*. It does not say why a business would buy it. This
module holds the derivation rules that bridge the two, plus the vocabulary the whole app shares
with `product_enrichment.json`: the trade list, the tag mapping and the material names.

Everything here is deliberately editable data rather than cleverness. When the store's tagging
changes, the maps below are the only thing that needs to change with it.
"""

from __future__ import annotations

import hashlib
import re

# The fixed trade list. It is the enum for AI enrichment, the vocabulary for knowledge-note and
# proven-fit matching, and the target of TAG_SEGMENT_MAP. It matches `segments` in
# `product_enrichment.json` exactly — if one changes, both must.
SEGMENTS: tuple[str, ...] = (
    "Gyms, studios and sports clubs",
    "Salons, barbers and beauty",
    "Cafés, restaurants and takeaways",
    "Bakeries and cake makers",
    "Clinics, dental and healthcare",
    "Offices and corporate teams",
    "Estate agents and property",
    "Event planners and venues",
    "Wedding planners and venues",
    "Schools and nurseries",
    "Independent shops and market stalls",
    "Hotels, B&Bs and holiday lets",
    "Mosques, charities and community groups",
    "Pet groomers, vets and kennels",
    "Kitchen, interior and trade businesses",
    "Freelancers, sole traders and creators",
)

SEGMENT_SET = frozenset(SEGMENTS)

# The store's real tags mapped onto trades. No listing uses the `segment:` prefix the importer
# originally expected, so without this every product arrived with no target segments at all.
TAG_SEGMENT_MAP: dict[str, tuple[str, ...]] = {
    "corporate": (
        "Offices and corporate teams",
        "Estate agents and property",
    ),
    "bizzsign": (
        "Salons, barbers and beauty",
        "Cafés, restaurants and takeaways",
        "Clinics, dental and healthcare",
        "Independent shops and market stalls",
    ),
    "baking": ("Bakeries and cake makers",),
    "celebrations": ("Event planners and venues",),
    "party": ("Event planners and venues",),
    "appreciation": (
        "Offices and corporate teams",
        "Gyms, studios and sports clubs",
    ),
    "housewarming": ("Estate agents and property",),
    "kids": ("Schools and nurseries",),
}

# Approved material names. The store's own catalogue notes forbid synonyms such as "plastic",
# "perspex", "hardwood" or "aluminum", so the canonical name is what gets stored.
_TAG_MATERIALS: dict[str, str] = {
    "wood": "plywood",
    "bamboo": "bamboo",
    "slate": "slate",
    "acrylic": "acrylic",
    "metal": "stainless steel",
    "cork": "cork",
}

_TITLE_MATERIALS: tuple[tuple[str, str], ...] = (
    ("mirror acrylic", "acrylic"),
    ("stainless steel", "stainless steel"),
    ("solid oak", "solid oak"),
    ("oak", "solid oak"),
    ("plywood", "plywood"),
    ("bamboo", "bamboo"),
    ("slate", "slate"),
    ("acrylic", "acrylic"),
    ("aluminium", "aluminium"),
    ("brass", "brass"),
    ("pu leather", "PU leather"),
    ("leather", "leather"),
    ("cork", "cork"),
    ("silicone", "silicone"),
)

# Titles that mean a business would buy this, not only a gift shopper.
_B2B_TITLE_WORDS: tuple[str, ...] = (
    "custom",
    "logo",
    "business",
    "corporate",
    "signage",
    "sign",
    "badge",
    "plaque",
)

_B2B_TAGS = frozenset({"corporate", "bizzsign"})

# En and em dashes, named rather than inlined so the source stays unambiguous.
_DASHES = chr(0x2013) + chr(0x2014)

# Price phrasing that must never reach a model or an email. Pricing is quoted per job.
_PRICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:from\s+)?£\s?\d+(?:[.,]\d{2})?(?:\s*(?:-|to)\s*£?\s?\d+(?:[.,]\d{2})?)?", re.I),
    re.compile(r"\bbundle and save\b[^.!?]*", re.I),
    # Order matters: consume the whole discount phrase, including any "%" and "off", or a
    # partial match leaves fragments such as "% off now" behind.
    re.compile(r"\bsave\s+(?:up to\s+)?£?\d+(?:[.,]\d{2})?\s*%?(?:\s*off)?", re.I),
    re.compile(r"\b\d+\s*%\s*off\b", re.I),
)


def strip_prices(value: str) -> str:
    """Remove price phrasing and tidy the punctuation it leaves behind."""
    cleaned = value
    for pattern in _PRICE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"([.,;:])\1+", r"\1", cleaned)
    return cleaned.strip(" -,;:" + _DASHES)


def source_hash(title: str, seo_description: str, tags: set[str]) -> str:
    """Fingerprint of the fields enrichment is derived from.

    Computed exactly as `product_enrichment.json` computed it, so a seeded product whose
    listing has since changed is detectable and can be re-enriched.
    """
    joined = ",".join(sorted(tags))
    payload = f"{title}{seo_description}{joined}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def derive_summary(seo_description: str, description: str) -> str | None:
    """A short, price-free line describing the product."""
    source = seo_description.strip() or description.strip()[:300]
    cleaned = strip_prices(source)
    return cleaned[:400] or None


def derive_category(product_type: str, product_category: str) -> str:
    """`Type` is filled on almost no listing, so fall back to the leaf of the taxonomy path."""
    if product_type.strip():
        return product_type.strip()[:200]
    leaf = product_category.split(">")[-1].strip()
    return (leaf or "Uncategorised")[:200]


def derive_materials(tags: set[str], title: str) -> list[str]:
    found: list[str] = []
    folded_tags = {tag.casefold() for tag in tags}
    for tag, material in _TAG_MATERIALS.items():
        if tag in folded_tags:
            found.append(material)
    folded_title = title.casefold()
    for needle, material in _TITLE_MATERIALS:
        if needle in folded_title:
            found.append(material)
    # Preserve first-seen order while removing duplicates: the most specific title match wins.
    return list(dict.fromkeys(found))


def derive_segments_from_tags(tags: set[str]) -> list[str]:
    found: list[str] = []
    folded = {tag.casefold() for tag in tags}
    for tag, segments in TAG_SEGMENT_MAP.items():
        if tag in folded:
            found.extend(segments)
    return sorted(set(found), key=str.casefold)


def derive_b2b_relevant(tags: set[str], title: str, explicit_segments: list[str]) -> bool:
    folded = {tag.casefold() for tag in tags}
    if folded & _B2B_TAGS or explicit_segments:
        return True
    folded_title = title.casefold()
    return any(word in folded_title for word in _B2B_TITLE_WORDS)
