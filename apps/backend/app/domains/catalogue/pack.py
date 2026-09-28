"""Shape of `product_enrichment.json`, the operator's sales-knowledge pack.

The pack is a local file the operator chooses to import, not a network payload. It is gitignored and
never committed, because it carries client names and the sales playbook. It is still parsed
strictly: a typo in a hand-edited pack should fail loudly at import rather than quietly put empty
strings in front of the assistant.

Its own rules, which this app enforces elsewhere:

- No prices anywhere. Pricing is quoted per job.
- `seed` enrichment may be replaced by a later AI run only when the listing has changed, and
  `manual` never.
- A `please_confirm` fit stays out of prospect-facing copy until the operator confirms it.
- A client is named in prospect-facing copy only when `share_client_name` is true.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _text(value: object) -> object:
    """The pack writes `null` for fields it has nothing for. Treat that as absent, not invalid."""
    return "" if value is None else value


def _items(value: object) -> object:
    return [] if value is None else value


Text = Annotated[str, BeforeValidator(_text)]
StringList = Annotated[list[str], BeforeValidator(_items)]


class PackProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")

    handle: str = Field(min_length=1, max_length=255)
    title: Text = Field(default="", max_length=300)
    listing_status: Text = Field(default="", max_length=40)
    url: Text = Field(default="", max_length=2048)
    category: Text = Field(default="", max_length=200)
    summary: Text = Field(default="", max_length=400)
    materials: StringList = Field(default_factory=list, max_length=20)
    sizes_and_packs: Text = Field(default="", max_length=400)
    colour_options: StringList = Field(default_factory=list, max_length=30)
    occasions: StringList = Field(default_factory=list, max_length=20)
    collections: StringList = Field(default_factory=list, max_length=30)
    b2b_relevant: bool = False
    bulk_ready: bool = False
    target_segments: StringList = Field(default_factory=list, max_length=20)
    example_use_cases: StringList = Field(default_factory=list, max_length=20)
    b2b_notes: Text = Field(default="", max_length=600)
    custom_options: Text = Field(default="", max_length=300)
    source_hash: Text = Field(default="", max_length=32)
    shopify_updated_at: Text = Field(default="", max_length=40)


class PackKnowledgeNote(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    segments: StringList = Field(default_factory=list, max_length=20)
    product_handles: StringList = Field(default_factory=list, max_length=60)
    body: str = Field(min_length=1, max_length=1_500)


class PackProvenFit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    segment: str = Field(min_length=1, max_length=120)
    client_label: Text = Field(default="", max_length=200)
    client_name: str | None = Field(default=None, max_length=200)
    share_client_name: bool = False
    products: StringList = Field(default_factory=list, max_length=30)
    use: Text = Field(default="", max_length=2_000)
    outcome: Text = Field(default="", max_length=400)
    status: Text = Field(default="please_confirm", max_length=40)


class EnrichmentPack(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    generated_at: datetime | None = None
    source: Text = Field(default="", max_length=300)
    segments: StringList = Field(default_factory=list, max_length=60)
    products: list[PackProduct] = Field(default_factory=list, max_length=2_000)
    knowledge_notes: list[PackKnowledgeNote] = Field(default_factory=list, max_length=200)
    proven_fits: list[PackProvenFit] = Field(default_factory=list, max_length=200)
