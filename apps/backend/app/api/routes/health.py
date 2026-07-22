from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.api.dependencies import Authenticated, DatabaseSession

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    application_version: str
    database: str
    time: datetime


@router.get("/health", response_model=HealthResponse)
def health(_: Authenticated, session: DatabaseSession) -> HealthResponse:
    session.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok", application_version=__version__, database="ok", time=datetime.now(UTC)
    )
