from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    INACTIVE = "inactive"


class DiscoveryMode(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    COMBINED = "combined"


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    segment: str = Field(min_length=1, max_length=100)
    primary_location: str = Field(min_length=1, max_length=200)
    radius_miles: float = Field(gt=0, le=500)
    keywords: list[str] = Field(default_factory=list, max_length=100)
    exclusion_keywords: list[str] = Field(default_factory=list, max_length=100)
    product_categories: list[str] = Field(default_factory=list, max_length=100)
    product_family_id: str | None = Field(default=None, min_length=36, max_length=36)
    discovery_sources: list[str] = Field(default_factory=lambda: ["manual"], max_length=20)
    weekly_shortlist_size: int = Field(default=5, ge=1, le=50)
    minimum_score_threshold: int = Field(default=0, ge=0, le=100)
    preferred_channels: list[str] = Field(default_factory=list, max_length=10)
    offer_settings: dict[str, bool] = Field(default_factory=dict)
    discovery_mode: DiscoveryMode = DiscoveryMode.MANUAL
    status: CampaignStatus = CampaignStatus.ACTIVE

    @field_validator(
        "keywords",
        "exclusion_keywords",
        "product_categories",
        "discovery_sources",
        "preferred_channels",
    )
    @classmethod
    def clean_list(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(set(item.casefold() for item in cleaned)):
            raise ValueError("List values must be unique")
        return cleaned

    @field_validator("discovery_sources")
    @classmethod
    def supported_sources(cls, values: list[str]) -> list[str]:
        if not set(values).issubset(
            {"manual", "google_places", "instagram", "public_registries"}
        ):
            raise ValueError("Discovery sources contain an unsupported provider")
        return values


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    segment: str
    primary_location: str
    radius_miles: float
    keywords: list[str]
    exclusion_keywords: list[str]
    product_categories: list[str]
    product_family_id: str | None
    discovery_sources: list[str]
    weekly_shortlist_size: int
    minimum_score_threshold: int
    preferred_channels: list[str]
    offer_settings: dict[str, bool]
    discovery_mode: str
    status: str
    created_at: datetime
    updated_at: datetime


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    segment: str | None = Field(default=None, min_length=1, max_length=100)
    primary_location: str | None = Field(default=None, min_length=1, max_length=200)
    radius_miles: float | None = Field(default=None, gt=0, le=500)
    keywords: list[str] | None = Field(default=None, max_length=100)
    exclusion_keywords: list[str] | None = Field(default=None, max_length=100)
    product_categories: list[str] | None = Field(default=None, max_length=100)
    product_family_id: str | None = Field(default=None, min_length=36, max_length=36)
    discovery_sources: list[str] | None = Field(default=None, max_length=20)
    weekly_shortlist_size: int | None = Field(default=None, ge=1, le=50)
    minimum_score_threshold: int | None = Field(default=None, ge=0, le=100)
    preferred_channels: list[str] | None = Field(default=None, max_length=10)
    offer_settings: dict[str, bool] | None = None
    discovery_mode: DiscoveryMode | None = None
    status: CampaignStatus | None = None

    @field_validator(
        "keywords",
        "exclusion_keywords",
        "product_categories",
        "discovery_sources",
        "preferred_channels",
    )
    @classmethod
    def clean_optional_list(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(set(item.casefold() for item in cleaned)):
            raise ValueError("List values must be unique")
        return cleaned

    @field_validator("discovery_sources")
    @classmethod
    def supported_optional_sources(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and not set(values).issubset(
            {"manual", "google_places", "instagram", "public_registries"}
        ):
            raise ValueError("Discovery sources contain an unsupported provider")
        return values

    @model_validator(mode="after")
    def require_change(self) -> CampaignUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one campaign field to update")
        return self


class CampaignDuplicate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    segment: str | None = Field(default=None, min_length=1, max_length=100)
    primary_location: str | None = Field(default=None, min_length=1, max_length=200)
    status: CampaignStatus = CampaignStatus.PAUSED
