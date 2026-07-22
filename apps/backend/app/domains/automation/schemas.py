from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domains.leads.identity import social_identity, valid_public_email


class CampaignRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CampaignRunProvider(StrEnum):
    SCORING = "scoring"
    GOOGLE_PLACES = "google_places"
    INSTAGRAM = "instagram"
    PUBLIC_REGISTRIES = "public_registries"


class CandidateStatus(StrEnum):
    DISCOVERED = "discovered"
    PROMOTED = "promoted"
    LINKED_EXISTING = "linked_existing"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"


class ProviderAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    status: str
    query: str
    request_count: int
    response_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class DiscoveryCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    campaign_id: str
    provider: str
    provider_record_id: str
    business_name: str
    location: str
    website: str | None
    phone: str | None
    source_url: str | None
    place_types: list[str]
    evidence: dict[str, object]
    status: str
    matched_lead_id: str | None
    duplicate_confidence: float | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class CampaignRunRead(BaseModel):
    id: str
    batch_id: str
    campaign_id: str
    campaign_name: str
    trigger: str
    status: str
    phase: str
    provider_status: str
    query_summary: str | None
    metrics: dict[str, int]
    warnings: list[str]
    error_code: str | None
    error_message: str | None
    cancellation_requested: bool
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    candidates: list[DiscoveryCandidateRead] = Field(default_factory=list)
    attempts: list[ProviderAttemptRead] = Field(default_factory=list)


class CampaignRunStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(min_length=36, max_length=36)
    provider: CampaignRunProvider


class CampaignRunAllStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: CampaignRunProvider


class CandidateDecisionAction(StrEnum):
    PROMOTE = "promote"
    LINK = "link"
    REJECT = "reject"


class CandidateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: CandidateDecisionAction
    lead_id: str | None = Field(default=None, min_length=36, max_length=36)
    reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def require_link_target(self) -> CandidateDecision:
        if self.action is CandidateDecisionAction.LINK and self.lead_id is None:
            raise ValueError("A lead ID is required when linking a candidate")
        return self


class SocialPlatform(StrEnum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class SocialCandidateCapture(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    campaign_id: str = Field(min_length=36, max_length=36)
    platform: SocialPlatform
    profile_url: HttpUrl
    business_name: str = Field(min_length=1, max_length=300)
    location: str = Field(min_length=1, max_length=500)
    website: HttpUrl | None = None
    phone_number: str | None = Field(default=None, max_length=100)
    public_email: str | None = Field(default=None, max_length=320)
    public_bio: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_public_identity(self) -> SocialCandidateCapture:
        social_identity(str(self.profile_url), self.platform.value)
        if self.public_email and not valid_public_email(self.public_email):
            raise ValueError("Provide a valid public email address")
        return self


class InstagramProfileLookup(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    profile_url: HttpUrl

    @model_validator(mode="after")
    def validate_instagram_profile(self) -> InstagramProfileLookup:
        social_identity(str(self.profile_url), SocialPlatform.INSTAGRAM.value)
        return self


class InstagramProfileImport(InstagramProfileLookup):
    campaign_id: str = Field(min_length=36, max_length=36)


class InstagramCampaignEnrichment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    campaign_id: str = Field(min_length=36, max_length=36)


class InstagramProfileRead(BaseModel):
    account_id: str
    username: str
    profile_url: str
    business_name: str
    biography: str | None
    website: str | None
    public_email: str | None
    public_phone: str | None
    followers_count: int | None
    media_count: int | None


class ProviderCapabilityRead(BaseModel):
    google_places_configured: bool
    instagram_configured: bool
    instagram_connected: bool
    instagram_account: str | None = None
    instagram_status: str
    website_enrichment_enabled: bool = True
    public_registries_available: bool = True
    maximum_results_per_campaign: int
    maximum_queries_per_campaign: int
    outbound_messaging: str = "disabled"
