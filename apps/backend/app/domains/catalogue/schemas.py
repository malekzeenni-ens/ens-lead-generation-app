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


class ShopifyImportResult(BaseModel):
    filename: str
    rows_read: int
    products_created: int
    products_updated: int
    products_skipped: int
    issues: list[ImportIssue]
