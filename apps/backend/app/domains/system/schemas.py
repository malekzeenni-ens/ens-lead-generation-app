from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkspaceSettings(BaseModel):
    retention_review_days: int = Field(default=365, ge=30, le=3650)
    follow_up_window_days: int = Field(default=7, ge=1, le=30)
    default_campaign_radius_miles: int = Field(default=25, ge=1, le=500)
    default_weekly_shortlist_size: int = Field(default=5, ge=1, le=50)


class WorkspaceSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retention_review_days: int | None = Field(default=None, ge=30, le=3650)
    follow_up_window_days: int | None = Field(default=None, ge=1, le=30)
    default_campaign_radius_miles: int | None = Field(default=None, ge=1, le=500)
    default_weekly_shortlist_size: int | None = Field(default=None, ge=1, le=50)

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
