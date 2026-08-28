from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class BackupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_directory: Path


class BackupVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup_path: Path


class BackupResult(BaseModel):
    backup_path: Path
    manifest_path: Path
    checksum_sha256: str = Field(min_length=64, max_length=64)
    integrity_result: str
    schema_version: str
    application_version: str
    created_at: datetime


class VerificationResult(BaseModel):
    valid: bool
    checksum_matches: bool
    integrity_result: str
    schema_version: str
