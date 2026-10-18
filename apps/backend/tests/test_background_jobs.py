"""Long AI work runs outside the request, with progress and cancellation (ADR-022)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import BackgroundJob
from app.db.session import Database
from app.domains.campaign_assistant.manager import CampaignAssistantManager
from app.domains.campaign_assistant.schemas import ResourceProfile
from app.jobs.manager import JobContext, JobManager
from app.jobs.schemas import BackgroundJobRead
from tests.test_campaign_assistant import FakeMonitor


def _wait_for(
    database: Database, job_id: str, statuses: set[str], timeout: float = 10.0
) -> BackgroundJobRead:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with database.session_factory() as session:
            job = session.get(BackgroundJob, job_id)
            if job is not None and job.status in statuses:
                return BackgroundJobRead.model_validate(job)
        time.sleep(0.02)
    raise AssertionError(f"Job {job_id} did not reach {statuses}")


@pytest.fixture
def jobs(client: TestClient, app: FastAPI) -> Any:
    manager = JobManager(app.state.database)
    yield manager
    manager.shutdown()


def _submit(jobs: JobManager, kind: str, handler: Callable[[Session, JobContext], Any]) -> str:
    jobs.register(kind, handler)
    with jobs.database.session_factory() as session:
        return jobs.submit(session, kind, {"items": 3}, "test").id


def test_a_job_reports_progress_and_stores_its_result(jobs: JobManager) -> None:
    def handler(session: Session, context: JobContext) -> dict[str, Any]:
        for index in range(context.payload["items"]):
            context.report_progress(index + 1, context.payload["items"])
        return {"done": True}

    job = _wait_for(jobs.database, _submit(jobs, "count", handler), {"succeeded"})
    assert job.result == {"done": True}
    assert (job.progress_current, job.progress_total) == (3, 3)
    assert job.started_at is not None and job.completed_at is not None


def test_a_job_is_cancelled_between_steps_and_keeps_its_progress(jobs: JobManager) -> None:
    first_step_done = threading.Event()

    def handler(session: Session, context: JobContext) -> dict[str, Any]:
        context.report_progress(1, 3)
        first_step_done.set()
        while not context.cancelled():
            time.sleep(0.01)
        context.raise_if_cancelled()
        return {}

    job_id = _submit(jobs, "slow", handler)
    assert first_step_done.wait(timeout=5)
    with jobs.database.session_factory() as session:
        assert jobs.cancel(session, job_id).cancellation_requested is True
    job = _wait_for(jobs.database, job_id, {"cancelled"})
    assert job.progress_current == 1


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (DomainError("LOCAL_AI_DISABLED", "Disabled."), "LOCAL_AI_DISABLED"),
        (RuntimeError("boom"), "JOB_FAILED"),
    ],
)
def test_a_failing_job_records_why(jobs: JobManager, failure: Exception, code: str) -> None:
    def handler(session: Session, context: JobContext) -> dict[str, Any]:
        raise failure

    job = _wait_for(jobs.database, _submit(jobs, "fails", handler), {"failed"})
    assert job.error_code == code
    assert job.error_message


def test_only_one_job_of_a_kind_when_asked(app: FastAPI, client: TestClient) -> None:
    jobs = JobManager(app.state.database)
    release = threading.Event()

    def wait_for_release(session: Session, context: JobContext) -> dict[str, Any]:
        release.wait(5)
        return {}

    jobs.register("single", wait_for_release)
    try:
        with app.state.database.session_factory() as session:
            first = jobs.submit(session, "single", {}, "t", one_at_a_time=True)
            with pytest.raises(DomainError) as refused:
                jobs.submit(session, "single", {}, "t", one_at_a_time=True)
        assert refused.value.code == "JOB_ALREADY_ACTIVE"
        assert refused.value.details == {"job_id": first.id}
    finally:
        release.set()
        jobs.shutdown()


def test_startup_requeues_waiting_jobs_and_closes_interrupted_ones(
    app: FastAPI, client: TestClient
) -> None:
    database: Database = app.state.database
    with database.session_factory() as session:
        running = BackgroundJob(kind="count", status="running", correlation_id="t")
        waiting = BackgroundJob(kind="count", status="queued", correlation_id="t")
        session.add_all([running, waiting])
        session.commit()
        running_id, waiting_id = running.id, waiting.id

    jobs = JobManager(database)
    jobs.register("count", lambda session, context: {"ran": True})
    try:
        jobs.recover()
        assert _wait_for(database, waiting_id, {"succeeded"}).result == {"ran": True}
        interrupted = _wait_for(database, running_id, {"interrupted"})
        assert interrupted.error_code == "JOB_INTERRUPTED"
    finally:
        jobs.shutdown()


class _SlowOllama:
    preferred_model = ""

    def __init__(self) -> None:
        self.calls = 0

    def generate_structured(self, *args: Any, **kwargs: Any) -> str:
        self.calls += 1
        return "generated"

    def unload(self) -> None:
        return

    def model_for(self, profile: ResourceProfile) -> str:
        return "llama3.2:3b"


def test_a_job_waits_for_the_model_and_can_be_cancelled_while_waiting(settings: Any) -> None:
    ollama = _SlowOllama()
    manager = CampaignAssistantManager(
        settings, ollama_client=cast(Any, ollama), monitor=cast(Any, FakeMonitor())
    )

    def generate(cancelled: Callable[[], bool]) -> Any:
        return manager.generate_structured(
            [],
            schema={},
            model_cls=cast(Any, object),
            error_prefix="TEST",
            protect_resources=False,
            cancelled=cancelled,
        )

    manager._generation_lock.acquire()  # an interactive request is using the model
    outcome: dict[str, Any] = {}
    waiter = threading.Thread(target=lambda: outcome.update(result=generate(lambda: False)))
    waiter.start()
    time.sleep(0.2)
    assert ollama.calls == 0
    manager._generation_lock.release()
    waiter.join(timeout=5)
    assert outcome["result"][0] == "generated"

    # An interactive request still fails fast while the model is busy.
    manager._generation_lock.acquire()
    try:
        with pytest.raises(DomainError) as busy:
            manager.generate_structured(
                [],
                schema={},
                model_cls=cast(Any, object),
                error_prefix="T",
                protect_resources=False,
            )
        assert busy.value.code == "CAMPAIGN_ASSISTANT_BUSY"
        with pytest.raises(InterruptedError):
            generate(lambda: True)
    finally:
        manager._generation_lock.release()


def test_jobs_api_lists_gets_and_cancels(client: TestClient, app: FastAPI) -> None:
    with app.state.database.session_factory() as session:
        job = BackgroundJob(kind="lead_autofill", status="queued", correlation_id="t")
        session.add(job)
        session.commit()
        job_id = job.id

    assert [item["id"] for item in client.get("/api/v1/jobs?active=true").json()] == [job_id]
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "queued"
    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert client.get("/api/v1/jobs?active=true").json() == []
    assert client.get("/api/v1/jobs/missing").status_code == 404


def test_catalogue_enrichment_runs_as_a_job(client: TestClient, app: FastAPI) -> None:
    from tests.test_lead_assistant import FakeStructuredManager
    from tests.test_product_knowledge import _import_csv

    _import_csv(client)
    proposal = {"target_segments": [], "example_use_cases": ["Gift"], "b2b_notes": "Useful."}
    app.state.campaign_assistant_manager = FakeStructuredManager([proposal, proposal])

    response = client.post("/api/v1/catalogue/enrichment/run", json={"limit": 2})

    assert response.status_code == 202, response.text
    job = response.json()
    assert job["kind"] == "catalogue_enrichment"
    assert job["status"] == "succeeded"
    assert job["result"]["products_enriched"] == 2
    assert job["progress_total"] == 2
