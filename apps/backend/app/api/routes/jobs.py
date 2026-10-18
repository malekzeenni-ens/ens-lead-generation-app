from typing import cast

from fastapi import APIRouter, Request

from app.api.dependencies import Authenticated, DatabaseSession
from app.jobs.manager import JobManager
from app.jobs.schemas import BackgroundJobRead

router = APIRouter(prefix="/jobs", tags=["background jobs"])


def job_manager(request: Request) -> JobManager:
    return cast(JobManager, request.app.state.job_manager)


@router.get("", response_model=list[BackgroundJobRead])
def list_jobs(
    request: Request, _: Authenticated, session: DatabaseSession, active: bool = False
) -> list[BackgroundJobRead]:
    return job_manager(request).list(session, active_only=active)


@router.get("/{job_id}", response_model=BackgroundJobRead)
def get_job(
    job_id: str, request: Request, _: Authenticated, session: DatabaseSession
) -> BackgroundJobRead:
    return job_manager(request).get(session, job_id)


@router.post("/{job_id}/cancel", response_model=BackgroundJobRead)
def cancel_job(
    job_id: str, request: Request, _: Authenticated, session: DatabaseSession
) -> BackgroundJobRead:
    return job_manager(request).cancel(session, job_id)
