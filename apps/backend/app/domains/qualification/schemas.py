from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScoringWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_relevance: int = Field(default=25, ge=0, le=100)
    activity: int = Field(default=10, ge=0, le=100)
    product_fit: int = Field(default=25, ge=0, le=100)
    local_relevance: int = Field(default=15, ge=0, le=100)
    commercial_potential: int = Field(default=5, ge=0, le=100)
    reach_credibility: int = Field(default=10, ge=0, le=100)
    contactability: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def require_total(self) -> ScoringWeights:
        if sum(self.model_dump().values()) != 100:
            raise ValueError("Scoring weights must total 100")
        return self


class ScoringProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    segment: str
    version: int
    weights: ScoringWeights
    active: bool
    created_at: datetime


class ScoringProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    weights: ScoringWeights


class ProductMatch(BaseModel):
    product_id: str
    product_name: str
    category: str
    match_score: int
    reason: str
    evidence: list[str]
    rule_based: bool = True


class CategoryBreakdown(BaseModel):
    category: str
    points_awarded: int
    points_available: int
    evidence_used: list[str]
    missing_evidence: list[str]
    ai_inference: None = None


class ScoreRunRead(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    profile_id: str
    profile_name: str
    profile_version: int
    rule_version: str
    campaign_run_id: str | None
    input_fingerprint: str | None
    calculated_score: int
    final_score: int
    manual_override: bool
    override_reason: str | None
    breakdown: list[CategoryBreakdown]
    product_matches: list[ProductMatch]
    created_at: datetime
    overridden_at: datetime | None


class ScoreCalculate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(min_length=36, max_length=36)


class ScoreOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    final_score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=3, max_length=2_000)


class ShortlistDecision(StrEnum):
    APPROVED = "approved"
    DEFERRED = "deferred"
    DISMISSED = "dismissed"
    REPLACE = "replace"


class ShortlistGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(min_length=36, max_length=36)
    week_start: date | None = None
    size: int | None = Field(default=None, ge=1, le=50)


class ShortlistAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: ShortlistDecision
    reason: str | None = Field(default=None, max_length=2_000)


class ShortlistItemRead(BaseModel):
    id: str
    lead_id: str
    business_name: str
    segment: str
    location: str
    pipeline_stage: str
    score: int
    rank: int
    decision: str
    reason: str
    product_matches: list[ProductMatch]
    created_at: datetime
    decided_at: datetime | None


class ShortlistRead(BaseModel):
    id: str
    campaign_id: str
    campaign_name: str
    week_start: date
    capacity: int
    status: str
    items: list[ShortlistItemRead]
    created_at: datetime
    updated_at: datetime
