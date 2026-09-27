from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import ALLOWED_OLLAMA_MODELS


def _validate_local_ai_model(value: str) -> str:
    """An empty string means "follow the configured default", which is the shipped state."""
    if value and value not in ALLOWED_OLLAMA_MODELS:
        allowed = ", ".join(sorted(ALLOWED_OLLAMA_MODELS))
        raise ValueError(f"The local model must be empty or one of: {allowed}")
    return value


class WorkspaceSettings(BaseModel):
    retention_review_days: int = Field(default=365, ge=30, le=3650)
    follow_up_window_days: int = Field(default=7, ge=1, le=30)
    default_campaign_radius_miles: int = Field(default=25, ge=1, le=500)
    default_weekly_shortlist_size: int = Field(default=5, ge=1, le=50)
    weekly_outreach_global_limit: int = Field(default=20, ge=1, le=100)
    local_campaign_assistant_enabled: bool = True
    protect_design_software_resources: bool = True
    local_ai_model: str = ""

    _check_model = field_validator("local_ai_model")(_validate_local_ai_model)


class WorkspaceSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retention_review_days: int | None = Field(default=None, ge=30, le=3650)
    follow_up_window_days: int | None = Field(default=None, ge=1, le=30)
    default_campaign_radius_miles: int | None = Field(default=None, ge=1, le=500)
    default_weekly_shortlist_size: int | None = Field(default=None, ge=1, le=50)
    weekly_outreach_global_limit: int | None = Field(default=None, ge=1, le=100)
    local_campaign_assistant_enabled: bool | None = None
    protect_design_software_resources: bool | None = None
    local_ai_model: str | None = None

    @field_validator("local_ai_model")
    @classmethod
    def check_local_ai_model(cls, value: str | None) -> str | None:
        return None if value is None else _validate_local_ai_model(value)

    @model_validator(mode="after")
    def require_change(self) -> WorkspaceSettingsUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one workspace setting to update")
        return self


class DiagnosticsRead(BaseModel):
    api_status: str
    database_status: str
    schema_version: str
    database_size_bytes: int
    journal_mode: str
    foreign_keys_enabled: bool
    data_directory: str
    log_directory: str
    campaigns: int
    leads: int
    audit_events: int
    backups: int
    products: int
    score_runs: int
    shortlists: int
    campaign_runs: int
    discovery_candidates: int
    provider_mode: str
    outbound_messaging: str


class OperationsSummary(BaseModel):
    campaigns: int
    active_campaigns: int
    leads: int
    suppressed_leads: int
    review_required: int
    open_follow_ups: int
    due_today: int
    overdue: int
    due_this_week: int
    products: int
    scored_leads: int
    shortlisted_this_week: int
    pipeline: dict[str, int]
