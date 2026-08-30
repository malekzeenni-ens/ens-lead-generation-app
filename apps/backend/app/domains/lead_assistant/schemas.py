from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LeadFilterTranslateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=300)


class LeadFilterTranslateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    stage: str | None = None
    suppressed: bool | None = None
    campaign_id: str | None = None
    source_type: str | None = None
    keyword: str | None = Field(default=None, max_length=300)


class LeadBriefingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=1_000)
    talking_points: list[str] = Field(min_length=1, max_length=3)
    watch_out_for: str | None = Field(default=None, max_length=500)


class LeadAutofillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_ids: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def require_unique(self) -> LeadAutofillRequest:
        if len(set(self.lead_ids)) != len(self.lead_ids):
            raise ValueError("Each selected lead may appear only once")
        return self


class LeadAutofillSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    personalisation_observation: str | None = Field(default=None, max_length=4_000)
    relevance_opportunity: str | None = Field(default=None, max_length=4_000)
    offer_angle: str | None = Field(default=None, max_length=4_000)
    desired_next_step: str | None = Field(default=None, max_length=2_000)


class LeadAutofillResultItem(BaseModel):
    lead_id: str
    business_name: str
    suggestion: LeadAutofillSuggestion | None
    skipped_reason: str | None = None


class LeadAutofillResponse(BaseModel):
    items: list[LeadAutofillResultItem]


class StalledLeadDigestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int | None = Field(default=None, ge=1, le=25)


class StalledLeadSuggestion(BaseModel):
    lead_id: str
    business_name: str
    days_stale: int
    suggested_action: str = Field(min_length=1, max_length=300)


class StalledLeadDigestResponse(BaseModel):
    generated_at: datetime
    items: list[StalledLeadSuggestion]


class DigestModelItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    lead_id: str
    suggested_action: str = Field(min_length=1, max_length=300)


class DigestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DigestModelItem] = Field(max_length=25)
