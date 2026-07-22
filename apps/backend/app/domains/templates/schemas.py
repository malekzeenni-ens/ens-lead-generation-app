from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic: str
    subject: str
    body: str
    product_family_ids: list[str]
    created_at: datetime
    updated_at: datetime


class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: str = Field(min_length=1, max_length=200)
    subject: str = Field(default="", max_length=300)
    body: str = Field(min_length=1, max_length=20_000)
    product_family_ids: list[str] = Field(default_factory=list, max_length=50)


class TemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, min_length=1, max_length=20_000)
    product_family_ids: list[str] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def require_change(self) -> TemplateUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one template field to update")
        return self
