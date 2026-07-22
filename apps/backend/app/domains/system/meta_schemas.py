from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class MetaConfigurationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    app_id: str = Field(min_length=5, max_length=40, pattern=r"^[0-9]+$")
    app_secret: SecretStr = Field(min_length=16, max_length=200)


class MetaAccountRead(BaseModel):
    page_id: str
    page_name: str
    instagram_account_id: str
    instagram_username: str


class MetaAccountSelect(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    page_id: str = Field(min_length=1, max_length=100)


class MetaConnectionRead(BaseModel):
    configured: bool
    connected: bool
    status: str
    callback_url: str
    graph_version: str
    accounts: list[MetaAccountRead] = Field(default_factory=list)
    selected_account: MetaAccountRead | None = None
    expires_at: datetime | None = None
    error_message: str | None = None


class MetaAuthorizationStartRead(BaseModel):
    authorization_url: str
    expires_at: datetime

    @field_validator("authorization_url")
    @classmethod
    def require_meta_https(cls, value: str) -> str:
        if not value.startswith("https://www.facebook.com/"):
            raise ValueError("Unexpected Meta authorization URL")
        return value
