"""Background jobs for long local AI work (ADR-022).

A feature endpoint submits a job and returns it at once; the job runs on a single worker thread,
reports progress, and can be cancelled between steps. One worker is enough: local generations
share one model lock, so jobs could not run model calls in parallel anyway.

Handlers raise `InterruptedError` when cancelled and `DomainError` for an expected failure. Any
other exception fails the job with a generic message and is logged with its traceback.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import BackgroundJob
from app.db.session import Database
from app.jobs.schemas import ACTIVE_STATUSES, BackgroundJobRead, JobStatus

logger = logging.getLogger(__name__)


@dataclass
class JobContext:
    """What a handler gets besides its session: the job's payload, progress and cancellation."""

    job_id: str
    payload: dict[str, Any]
    correlation_id: str
    _session: Session
    _job: BackgroundJob
    _cancelled: Callable[[], bool]

    def cancelled(self) -> bool:
        return self._cancelled()

    def raise_if_cancelled(self) -> None:
        if self._cancelled():
            raise InterruptedError("Background job cancelled")

    def report_progress(self, current: int, total: int) -> None:
        """Record progress. This commits the session, so work done up to here is kept."""
        self._job.progress_current = current
        self._job.progress_total = total
        self._session.commit()


Handler = Callable[[Session, JobContext], dict[str, Any]]


class JobManager:
    def __init__(self, database: Database, *, inline: bool = False) -> None:
        self.database = database
        self.inline = inline
        self._handlers: dict[str, Handler] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="background-job")
        self._cancel_requested: set[str] = set()
        self._lock = threading.Lock()
        self._stopping = threading.Event()

    def register(self, kind: str, handler: Handler) -> None:
        self._handlers[kind] = handler

    def submit(
        self,
        session: Session,
        kind: str,
        payload: dict[str, Any],
        correlation_id: str,
        *,
        one_at_a_time: bool = False,
    ) -> BackgroundJobRead:
        if kind not in self._handlers:
            raise ValueError(f"No handler is registered for {kind}")
        if one_at_a_time:
            active = session.scalar(
                select(BackgroundJob.id).where(
                    BackgroundJob.kind == kind,
                    BackgroundJob.status.in_([status.value for status in ACTIVE_STATUSES]),
                )
            )
            if active is not None:
                raise DomainError(
                    "JOB_ALREADY_ACTIVE",
                    "This job is already running. Wait for it to finish or cancel it.",
                    status_code=409,
                    details={"job_id": active},
                )
        job = BackgroundJob(kind=kind, payload=payload, correlation_id=correlation_id[:100])
        session.add(job)
        session.commit()
        logger.info(
            "Background job queued",
            extra={"job_id": job.id, "job_kind": kind, "correlation_id": correlation_id},
        )
        if self.inline:
            self._execute(job.id)
            session.refresh(job)
        else:
            self._executor.submit(self._execute, job.id)
        return BackgroundJobRead.model_validate(job)

    def get(self, session: Session, job_id: str) -> BackgroundJobRead:
        job = session.get(BackgroundJob, job_id)
        if job is None:
            raise DomainError("JOB_NOT_FOUND", "Background job not found.", status_code=404)
        return BackgroundJobRead.model_validate(job)

    def list(self, session: Session, *, active_only: bool) -> list[BackgroundJobRead]:
        statement = select(BackgroundJob).order_by(BackgroundJob.created_at.desc()).limit(50)
        if active_only:
            statement = statement.where(
                BackgroundJob.status.in_([status.value for status in ACTIVE_STATUSES])
            )
        return [BackgroundJobRead.model_validate(job) for job in session.scalars(statement)]

    def cancel(self, session: Session, job_id: str) -> BackgroundJobRead:
        job = session.get(BackgroundJob, job_id)
        if job is None:
            raise DomainError("JOB_NOT_FOUND", "Background job not found.", status_code=404)
        if job.status in {status.value for status in ACTIVE_STATUSES}:
            job.cancellation_requested = True
            with self._lock:
                self._cancel_requested.add(job_id)
            if job.status == JobStatus.QUEUED.value:
                self._finish(job, JobStatus.CANCELLED)
            session.commit()
            logger.info("Background job cancellation requested", extra={"job_id": job_id})
        return BackgroundJobRead.model_validate(job)

    def recover(self) -> None:
        """At startup: requeue jobs that never started, and close jobs a stopped app cut off."""
        with self.database.session_factory() as session:
            jobs = list(
                session.scalars(
                    select(BackgroundJob).where(
                        BackgroundJob.status.in_([status.value for status in ACTIVE_STATUSES])
                    )
                )
            )
            queued: list[str] = []
            for job in jobs:
                if job.status == JobStatus.RUNNING.value:
                    job.error_code = "JOB_INTERRUPTED"
                    job.error_message = "The app closed before this job finished. Start it again."
                    self._finish(job, JobStatus.INTERRUPTED)
                elif job.kind in self._handlers:
                    queued.append(job.id)
                else:
                    job.error_code = "JOB_KIND_UNKNOWN"
                    job.error_message = "This kind of job is no longer supported."
                    self._finish(job, JobStatus.FAILED)
            session.commit()
            interrupted = [job.id for job in jobs if job.status == JobStatus.INTERRUPTED.value]
        if interrupted:
            logger.warning(
                "Background jobs interrupted by a previous shutdown", extra={"job_ids": interrupted}
            )
        for job_id in queued:
            self._executor.submit(self._execute, job_id)

    def shutdown(self) -> None:
        # Running handlers stop at their next cancellation check; the job is then marked
        # interrupted, because the app, not the operator, stopped it.
        self._stopping.set()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._stopping.is_set() or job_id in self._cancel_requested

    @staticmethod
    def _finish(job: BackgroundJob, status: JobStatus) -> None:
        job.status = status.value
        job.completed_at = datetime.now(UTC)

    def _execute(self, job_id: str) -> None:
        started = time.monotonic()
        with self.database.session_factory() as session:
            job = session.get(BackgroundJob, job_id)
            if job is None or job.status != JobStatus.QUEUED.value:
                return
            handler = self._handlers[job.kind]
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.now(UTC)
            session.commit()
            log_context = {"job_id": job_id, "job_kind": job.kind}
            logger.info("Background job started", extra=log_context)
            context = JobContext(
                job_id=job_id,
                payload=dict(job.payload),
                correlation_id=job.correlation_id,
                _session=session,
                _job=job,
                _cancelled=lambda: self._cancelled(job_id),
            )
            try:
                result = handler(session, context)
            except InterruptedError:
                session.rollback()
                job = self._reload(session, job_id)
                if self._stopping.is_set():
                    job.error_code = "JOB_INTERRUPTED"
                    job.error_message = "The app closed before this job finished. Start it again."
                    self._finish(job, JobStatus.INTERRUPTED)
                else:
                    self._finish(job, JobStatus.CANCELLED)
                session.commit()
                logger.info("Background job stopped", extra={**log_context, "status": job.status})
                return
            except DomainError as exc:
                session.rollback()
                job = self._reload(session, job_id)
                job.error_code = exc.code
                job.error_message = exc.message
                self._finish(job, JobStatus.FAILED)
                session.commit()
                logger.warning(
                    "Background job failed", extra={**log_context, "error_code": exc.code}
                )
                return
            except Exception:
                session.rollback()
                logger.exception("Background job failed unexpectedly", extra=log_context)
                job = self._reload(session, job_id)
                job.error_code = "JOB_FAILED"
                job.error_message = "The job failed safely; nothing it had not saved was kept."
                self._finish(job, JobStatus.FAILED)
                session.commit()
                return
            finally:
                with self._lock:
                    self._cancel_requested.discard(job_id)
            job.result = result
            self._finish(job, JobStatus.SUCCEEDED)
            session.commit()
            logger.info(
                "Background job succeeded",
                extra={**log_context, "duration_seconds": round(time.monotonic() - started, 1)},
            )

    @staticmethod
    def _reload(session: Session, job_id: str) -> BackgroundJob:
        job = session.get(BackgroundJob, job_id)
        if job is None:
            raise RuntimeError(f"Background job {job_id} disappeared while running")
        return job
