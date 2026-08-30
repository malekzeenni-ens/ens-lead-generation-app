from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssistantAttachmentUpload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=120)
    content_base64: str = Field(min_length=1, max_length=28_000_000)


class AssistantConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)


class AssistantContextSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["workspace", "campaign", "lead", "outreach_batch", "shortlist"] = "workspace"
    id: str | None = Field(default=None, min_length=36, max_length=36)

    @model_validator(mode="after")
    def validate_reference(self) -> AssistantContextSelection:
        if self.kind == "workspace" and self.id is not None:
            raise ValueError("Whole-workspace context must not include a record ID")
        if self.kind != "workspace" and self.id is None:
            raise ValueError("A record ID is required for the selected assistant context")
        return self


class AssistantMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=8_000)
    attachments: list[AssistantAttachmentUpload] = Field(default_factory=list, max_length=4)
    context: AssistantContextSelection = Field(default_factory=AssistantContextSelection)


class AssistantAttachmentRead(BaseModel):
    id: str
    direction: str
    filename: str
    media_type: str
    size_bytes: int
    processing_status: str
    download_url: str
    created_at: datetime


class AssistantMessageRead(BaseModel):
    id: str
    role: str
    content: str
    model_name: str | None
    resource_profile: str | None
    generation_duration_ms: int | None
    campaign_draft_suggested: bool
    attachments: list[AssistantAttachmentRead]
    created_at: datetime


class AssistantConversationRead(BaseModel):
    id: str
    title: str
    messages: list[AssistantMessageRead]
    created_at: datetime
    updated_at: datetime
