from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ContactClassification(StrEnum):
    CORPORATE = "corporate_subscriber"
    SOLE_TRADER = "sole_trader_or_individual"
    PARTNERSHIP = "partnership_individual_treatment"
    UNKNOWN = "unknown"


class EvidenceClassification(StrEnum):
    VERIFIED = "verified"
    USER_VERIFIED = "user_verified"
    USER_OBSERVED = "user_observed"
    PROVIDER_OBSERVED = "provider_observed"
    INFERRED = "inferred"
    SUGGESTED = "suggested"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    MANUAL = "manual"
    CSV = "csv"
    GOOGLE = "google"
    WEBSITE = "website"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    OTHER = "other"


class PipelineStage(StrEnum):
    NEW = "new"
    RESEARCHING = "researching"
    QUALIFIED = "qualified"
    RECOMMENDED_THIS_WEEK = "recommended_this_week"
    READY_TO_CONTACT = "ready_to_contact"
    CONTACTED = "contacted"
    FOLLOW_UP_DUE = "follow_up_due"
    REPLIED = "replied"
    MOCK_UP_REQUESTED = "mock_up_requested"
    SAMPLE_CONSIDERATION = "sample_consideration"
    QUOTE_REQUESTED = "quote_requested"
    QUOTE_SENT = "quote_sent"
    NEGOTIATING = "negotiating"
    WON = "won"
    LOST = "lost"
    NOT_SUITABLE = "not_suitable"
    DO_NOT_CONTACT = "do_not_contact"


class FollowUpType(StrEnum):
    EMAIL = "email"
    INSTAGRAM = "instagram"
    MOCK_UP = "mock_up"
    SAMPLE = "sample"
    QUOTE = "quote"
    GENERAL = "general"


class FollowUpStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LostReason(StrEnum):
    NO_RESPONSE = "no_response"
    NOT_INTERESTED = "not_interested"
    PRICE = "price"
    NO_CURRENT_NEED = "no_current_need"
    ALREADY_HAS_SUPPLIER = "already_has_supplier"
    OUTSIDE_SCOPE = "outside_scope"
    OTHER = "other"


class MockUpStatus(StrEnum):
    NOT_OFFERED = "not_offered"
    OFFERED = "offered"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    SENT = "sent"
    APPROVED = "approved"
    REJECTED = "rejected"


class SampleStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    UNDER_CONSIDERATION = "under_consideration"
    APPROVED = "approved"
    SENT = "sent"
    DECLINED = "declined"


class QuoteStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    PREPARING = "preparing"
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class CommunicationChannel(StrEnum):
    EMAIL = "email"
    INSTAGRAM = "instagram"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class CommunicationStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    RECEIVED = "received"
    RECORDED = "recorded"


class ResponseStatus(StrEnum):
    NONE = "none"
    REPLIED = "replied"
    NO_RESPONSE = "no_response"


class SuppressionType(StrEnum):
    DO_NOT_CONTACT = "do_not_contact"
    UNSUBSCRIBE = "unsubscribe"
    OBJECTION = "objection"


class ManualSourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(default="Manual entry", min_length=1, max_length=100)
    source_type: SourceType = SourceType.MANUAL
    source_url: HttpUrl | None = None
    classification: EvidenceClassification = EvidenceClassification.USER_VERIFIED
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    campaign_id: str = Field(min_length=36, max_length=36)
    business_name: str = Field(min_length=1, max_length=200)
    segment: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=200)
    website: HttpUrl | None = None
    social_profile: HttpUrl | None = None
    instagram_url: HttpUrl | None = None
    facebook_url: HttpUrl | None = None
    phone_number: str | None = Field(default=None, max_length=100)
    public_email: str | None = Field(default=None, max_length=320)
    contact_classification: ContactClassification = ContactClassification.UNKNOWN
    source: ManualSourceInput

    @model_validator(mode="after")
    def require_public_route(self) -> LeadCreate:
        if not any((self.website, self.social_profile, self.instagram_url, self.facebook_url)):
            raise ValueError("Provide a website or social profile for source traceability")
        from app.domains.leads.identity import social_identity, valid_public_email

        if self.public_email and not valid_public_email(self.public_email):
            raise ValueError("Provide a valid public email address")
        if self.instagram_url:
            social_identity(str(self.instagram_url), "instagram")
        if self.facebook_url:
            social_identity(str(self.facebook_url), "facebook")
        return self


class SocialIdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: str
    profile_url: str
    normalized_handle: str
    source_url: str | None
    classification: str
    collected_at: datetime


class SourceObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_name: str
    source_type: str
    field_name: str
    observed_value: str
    classification: str
    source_url: str | None
    collection_method: str
    collected_at: datetime


class StageEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    previous_stage: str | None
    new_stage: str
    actor: str
    reason: str | None
    created_at: datetime


class LeadNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content: str
    actor: str
    created_at: datetime


class FollowUpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    follow_up_type: str
    due_date: date
    status: str
    notes: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CommunicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel: str
    subject: str | None
    content: str
    draft_status: str
    approval_status: str
    sent_status: str
    sent_at: datetime | None
    user_confirmed: bool
    external_message_id: str | None
    response_status: str
    created_at: datetime


class SuppressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    suppression_type: str
    reason: str
    source: str
    notes: str | None
    active: bool
    effective_at: datetime
    lifted_at: datetime | None


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    segment: str
    location: str
    website: str | None
    social_profile: str | None
    phone_number: str | None
    public_email: str | None
    social_identities: list[SocialIdentityRead]
    contact_classification: str
    pipeline_stage: str
    suppressed: bool
    estimated_order_value: float | None
    quote_value: float | None
    won_value: float | None
    potential_recurrence: str | None
    lost_reason: str | None
    mock_up_status: str
    sample_status: str
    quote_status: str
    retention_review_date: date | None
    current_score: int | None
    score_updated_at: datetime | None
    campaign_ids: list[str]
    sources: list[SourceObservationRead]
    stage_events: list[StageEventRead]
    notes: list[LeadNoteRead]
    follow_ups: list[FollowUpRead]
    communications: list[CommunicationRead]
    suppression_records: list[SuppressionRead]
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    business_name: str | None = Field(default=None, min_length=1, max_length=200)
    segment: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    website: HttpUrl | None = None
    social_profile: HttpUrl | None = None
    instagram_url: HttpUrl | None = None
    facebook_url: HttpUrl | None = None
    phone_number: str | None = Field(default=None, max_length=100)
    public_email: str | None = Field(default=None, max_length=320)
    contact_classification: ContactClassification | None = None
    estimated_order_value: float | None = Field(default=None, ge=0)
    quote_value: float | None = Field(default=None, ge=0)
    won_value: float | None = Field(default=None, ge=0)
    potential_recurrence: str | None = Field(default=None, max_length=100)
    lost_reason: LostReason | None = None
    mock_up_status: MockUpStatus | None = None
    sample_status: SampleStatus | None = None
    quote_status: QuoteStatus | None = None
    retention_review_date: date | None = None

    @model_validator(mode="after")
    def require_change(self) -> LeadUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one lead field to update")
        from app.domains.leads.identity import social_identity, valid_public_email

        if self.public_email and not valid_public_email(self.public_email):
            raise ValueError("Provide a valid public email address")
        if self.instagram_url:
            social_identity(str(self.instagram_url), "instagram")
        if self.facebook_url:
            social_identity(str(self.facebook_url), "facebook")
        return self


class StageChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    stage: PipelineStage
    reason: str | None = Field(default=None, max_length=2_000)


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=10_000)


class FollowUpCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    follow_up_type: FollowUpType
    due_date: date
    notes: str | None = Field(default=None, max_length=2_000)


class FollowUpComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_follow_up: FollowUpCreate | None = None


class CommunicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    channel: CommunicationChannel
    subject: str | None = Field(default=None, max_length=300)
    content: str = Field(min_length=1, max_length=50_000)
    sent_status: CommunicationStatus = CommunicationStatus.RECORDED
    user_confirmed: bool = False
    external_message_id: str | None = Field(default=None, max_length=300)
    response_status: ResponseStatus = ResponseStatus.NONE

    @model_validator(mode="after")
    def require_manual_confirmation(self) -> CommunicationCreate:
        if self.sent_status is CommunicationStatus.SENT and not self.user_confirmed:
            raise ValueError("Manual sent communications require user confirmation")
        return self


class SuppressionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    suppression_type: SuppressionType
    reason: str = Field(min_length=1, max_length=2_000)
    source: str = Field(default="Local user", min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)


class LeadDeleteResult(BaseModel):
    deleted: bool
    suppression_evidence_retained: bool
