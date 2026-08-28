from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OutreachLeadOptionRead(BaseModel):
    id: str
    business_name: str
    location: str
    pipeline_stage: str
    public_email: str | None
    contact_classification: str
    current_score: int | None
    outreach_hold_until: date | None
    outreach_hold_reason: str | None
    ready: bool
    blockers: list[str]
    warnings: list[str]
    latest_notes: list[str]


class OutreachBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_ids: list[str] = Field(min_length=1, max_length=50)
    template_id: str = Field(min_length=36, max_length=36)
    campaign_id: str | None = Field(default=None, min_length=36, max_length=36)

    @model_validator(mode="after")
    def require_unique_leads(self) -> OutreachBatchCreate:
        if len(set(self.lead_ids)) != len(self.lead_ids):
            raise ValueError("Each selected lead may appear only once")
        return self


class OutreachDraftEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=50_000)


class OutreachDraftReject(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=2_000)


class OutreachZohoOpenFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2_000)


class OutreachDraftApproveMany(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_ids: list[str] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def require_unique_drafts(self) -> OutreachDraftApproveMany:
        if len(set(self.draft_ids)) != len(self.draft_ids):
            raise ValueError("Each draft may appear only once")
        return self


class OutreachDraftRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    subject: str
    body: str
    content_hash: str
    editor: str
    created_at: datetime


class OutreachDraftRead(BaseModel):
    id: str
    batch_id: str
    lead_id: str
    business_name: str
    location: str
    pipeline_stage: str
    recipient_email: str
    contact_classification: str
    current_score: int | None
    outreach_hold_until: date | None
    outreach_hold_reason: str | None
    latest_notes: list[str]
    template_id: str | None
    review_status: str
    sync_status: str
    current_version: int
    approved_version: int | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    blocked_reason: str | None
    current_revision: OutreachDraftRevisionRead
    revision_count: int
    created_at: datetime
    updated_at: datetime


class OutreachZohoHandoffRead(BaseModel):
    draft_id: str
    lead_id: str
    recipient_email: str
    subject: str
    body: str
    version: int
    opened_at: datetime


class OutreachBatchRead(BaseModel):
    id: str
    campaign_id: str | None
    template_id: str | None
    template_topic: str | None
    status: str
    pending_count: int
    approved_count: int
    rejected_count: int
    sent_count: int
    drafts: list[OutreachDraftRead]
    created_at: datetime
    updated_at: datetime
