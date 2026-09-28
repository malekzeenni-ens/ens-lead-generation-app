from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shopify_handle: str | None
    name: str
    category: str
    description: str
    target_segments: list[str]
    example_use_cases: list[str]
    image_reference: str | None
    active: bool
    pricing_guidance: str | None
    sample_eligible: bool
    source: str
    variant_count: int
    summary: str | None
    materials: list[str]
    occasions: list[str]
    product_url: str | None
    b2b_relevant: bool
    bulk_ready: bool
    b2b_notes: str | None
    custom_options: str | None
    enrichment_source: str
    stale_enrichment: bool
    last_seen_import_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20_000)
    target_segments: list[str] = Field(default_factory=list, max_length=30)
    example_use_cases: list[str] = Field(default_factory=list, max_length=30)
    image_reference: str | None = Field(default=None, max_length=2_048)
    active: bool = True
    pricing_guidance: str | None = Field(default=None, max_length=200)
    sample_eligible: bool = False
    summary: str | None = Field(default=None, max_length=400)
    materials: list[str] = Field(default_factory=list, max_length=20)
    occasions: list[str] = Field(default_factory=list, max_length=20)
    b2b_relevant: bool = False
    bulk_ready: bool = False
    b2b_notes: str | None = Field(default=None, max_length=600)
    custom_options: str | None = Field(default=None, max_length=300)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20_000)
    target_segments: list[str] | None = Field(default=None, max_length=30)
    example_use_cases: list[str] | None = Field(default=None, max_length=30)
    image_reference: str | None = Field(default=None, max_length=2_048)
    active: bool | None = None
    pricing_guidance: str | None = Field(default=None, max_length=200)
    sample_eligible: bool | None = None
    summary: str | None = Field(default=None, max_length=400)
    materials: list[str] | None = Field(default=None, max_length=20)
    occasions: list[str] | None = Field(default=None, max_length=20)
    b2b_relevant: bool | None = None
    bulk_ready: bool | None = None
    b2b_notes: str | None = Field(default=None, max_length=600)
    custom_options: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def require_change(self) -> ProductUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one product field to update")
        return self


class ProductFamilyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    products: list[ProductRead]
    created_at: datetime
    updated_at: datetime


class ProductFamilyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    product_ids: list[str] = Field(default_factory=list, max_length=500)


class ProductFamilyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    product_ids: list[str] | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_change(self) -> ProductFamilyUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one product family field to update")
        return self


class ShopifyCsvImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255, pattern=r"(?i)^.+\.csv$")
    content: str = Field(min_length=1, max_length=5_000_000)


class ImportIssue(BaseModel):
    handle: str | None
    message: str


class EnrichmentImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255, pattern=r"(?i)^.+\.json$")
    content: str = Field(min_length=1, max_length=5_000_000)


class EnrichmentImportResult(BaseModel):
    filename: str
    products_matched: int
    products_enriched: int
    products_unmatched: int
    notes_created: int
    notes_updated: int
    fits_created: int
    fits_skipped: int
    products_awaiting_enrichment: int
    fits_awaiting_confirmation: int
    issues: list[ImportIssue]


class KnowledgeNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    segments: list[str]
    product_handles: list[str]
    body: str
    source: str
    manual: bool
    updated_at: datetime


class KnowledgeNoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=1_500)
    segments: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def require_change(self) -> KnowledgeNoteUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one knowledge note field to update")
        return self


class ProvenFitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    segment: str
    product_handles: list[str]
    use: str
    outcome: str
    client_label: str
    client_name: str | None
    share_client_name: bool
    status: str
    lead_id: str | None
    created_at: datetime


class ProvenFitUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: str | None = Field(default=None, pattern=r"^(confirmed|please_confirm)$")
    share_client_name: bool | None = None
    client_label: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def require_change(self) -> ProvenFitUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one proven fit field to update")
        return self


class EnrichmentStatus(BaseModel):
    catalogue_imported_at: datetime | None
    catalogue_stale: bool
    products_total: int
    products_enriched: int
    products_awaiting_enrichment: int
    products_stale_enrichment: int
    knowledge_notes: int
    proven_fits: int
    fits_awaiting_confirmation: int


class EnrichmentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Refreshing a changed listing is opt-in: the seed pack is better than what a small local
    # model produces, so it is never replaced without the operator asking.
    include_stale: bool = False
    limit: int = Field(default=25, ge=1, le=200)


class EnrichmentRunResult(BaseModel):
    products_considered: int
    products_enriched: int
    products_failed: int
    notes_refreshed: int
    products_awaiting_enrichment: int
    issues: list[ImportIssue]


class ShopifyImportResult(BaseModel):
    filename: str
    rows_read: int
    products_created: int
    products_updated: int
    products_skipped: int
    products_deactivated: int = 0
    issues: list[ImportIssue]
