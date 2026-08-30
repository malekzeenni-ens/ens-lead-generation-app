from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.campaigns.schemas import CampaignCreate, CampaignRead, CampaignUpdate


class ResourceProfile(StrEnum):
    STANDARD = "standard"
    DESIGN_SOFTWARE = "design_software"


class DraftStatus(StrEnum):
    GENERATING = "generating"
    AWAITING_INPUT = "awaiting_input"
    AWAITING_OVERRIDE_CONFIRMATION = "awaiting_override_confirmation"
    READY = "ready"
    GENERATION_FAILED = "generation_failed"
    APPROVED = "approved"
    DISCARDED = "discarded"


class ProposalOutcome(StrEnum):
    DRAFT_READY = "draft_ready"
    CLARIFICATION_REQUIRED = "clarification_required"
    CONFIRMATION_REQUIRED = "confirmation_required"
    OVERRIDE_NOT_ALLOWED = "override_not_allowed"


class OverrideDecisionValue(StrEnum):
    CONFIRM = "confirm"
    REJECT = "reject"
    PARTIAL = "partial"


class OverrideItemProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str = Field(min_length=1, max_length=100)
    field: str = Field(min_length=1, max_length=100)
    playbook_recommendation: Any
    requested_value: Any
    impact: str = Field(min_length=1, max_length=1_000)


class OverrideRequestProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=1_000)
    items: list[OverrideItemProposal] = Field(min_length=1, max_length=12)


class CampaignDraftProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome: ProposalOutcome
    assistant_message: str = Field(min_length=1, max_length=3_000)
    questions: list[str] = Field(default_factory=list, max_length=3)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    campaign: CampaignCreate | None = None
    override_request: OverrideRequestProposal | None = None

    @model_validator(mode="after")
    def require_outcome_payload(self) -> CampaignDraftProposal:
        if self.outcome == ProposalOutcome.DRAFT_READY and self.campaign is None:
            raise ValueError("A ready proposal requires a complete campaign")
        if self.outcome == ProposalOutcome.CLARIFICATION_REQUIRED and not self.questions:
            raise ValueError("A clarification proposal requires at least one question")
        if self.outcome == ProposalOutcome.CONFIRMATION_REQUIRED and self.override_request is None:
            raise ValueError("An override proposal requires override details")
        if (
            self.outcome != ProposalOutcome.CONFIRMATION_REQUIRED
            and self.override_request is not None
        ):
            raise ValueError("Override details are only allowed when confirmation is required")
        return self


class CampaignDraftGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=2, max_length=2_000)


class CampaignDraftMessage(CampaignDraftGenerate):
    expected_version: int = Field(ge=1)


class CampaignDraftManualUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    changes: CampaignUpdate


class OverrideDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    decision: OverrideDecisionValue
    confirmed_item_ids: list[str] = Field(default_factory=list, max_length=12)


class CampaignDraftApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class OverrideItemRead(OverrideItemProposal):
    item_id: str
    decision: Literal["pending", "confirmed", "rejected"] = "pending"


class CampaignDraftOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    draft_id: str
    draft_version: int
    status: str
    summary: str
    items: list[OverrideItemRead]
    playbook_version: str
    created_at: datetime
    confirmed_at: datetime | None
    rejected_at: datetime | None


class CampaignDraftRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    revision_source: str
    user_instruction: str | None
    payload: CampaignCreate | None
    assistant_message: str
    assumptions: list[str]
    warnings: list[str]
    questions: list[str]
    resource_profile: str
    model_name: str
    prompt_version: str
    created_at: datetime


class CampaignDraftRead(BaseModel):
    id: str
    status: str
    original_request: str
    campaign: CampaignCreate | None
    assistant_message: str
    assumptions: list[str]
    warnings: list[str]
    questions: list[str]
    version: int
    model_name: str
    prompt_version: str
    resource_profile: str
    generation_duration_ms: int | None
    prompt_token_count: int | None
    output_token_count: int | None
    approved_campaign_id: str | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    overrides: list[CampaignDraftOverrideRead] = Field(default_factory=list)
    revisions: list[CampaignDraftRevisionRead] = Field(default_factory=list)


class AssistantStatusRead(BaseModel):
    enabled: bool
    ollama_reachable: bool
    model_installed: bool
    model_loaded: bool
    model: str
    resource_profile: ResourceProfile
    protected_applications: list[str]
    ready: bool
    message: str


class CampaignDraftApprovalResult(BaseModel):
    draft: CampaignDraftRead
    campaign: CampaignRead


class OllamaGenerationMetrics(BaseModel):
    model: str
    model_digest: str | None = None
    total_duration_ms: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None
