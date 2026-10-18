from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # The app stopped while the job ran, and the job cannot pick up where it left off.
    INTERRUPTED = "interrupted"


ACTIVE_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.RUNNING})


class BackgroundJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: JobStatus
    progress_current: int
    progress_total: int
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    cancellation_requested: bool
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
