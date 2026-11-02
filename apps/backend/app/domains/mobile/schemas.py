from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A Tailscale MagicDNS name such as "ens-pc.tail1a2b3c.ts.net".
_TAILSCALE_HOST = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+ts\.net$")


def validate_public_host(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    if value and not _TAILSCALE_HOST.fullmatch(value):
        raise ValueError("The phone address must be this PC's Tailscale name, ending in .ts.net")
    return value


class MobileAccessConfig(BaseModel):
    enabled: bool = False
    public_host: str = ""

    _check_host = field_validator("public_host")(validate_public_host)


class MobileAccessConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    public_host: str | None = None

    @field_validator("public_host")
    @classmethod
    def check_host(cls, value: str | None) -> str | None:
        return None if value is None else validate_public_host(value)


class MobileAccessStatus(BaseModel):
    enabled: bool
    running: bool
    port: int
    public_host: str
    phone_url: str | None
    error: str | None
    paired_devices: int


class PairingCodeRead(BaseModel):
    code: str
    expires_at: datetime
    pair_url: str | None


class PairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=4, max_length=20)
    name: str = Field(min_length=1, max_length=60)
    label: str = Field(default="", max_length=60)


class MobileDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    label: str
    created_at: datetime
    last_seen_at: datetime


class MobileSessionRead(BaseModel):
    channel: str
    device: MobileDeviceRead | None
