"""The backend schedules weekly outreach while the app runs (FR-060, decision D5)."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.models import CampaignRun
from app.domains.automation.manager import CampaignRunManager
from app.domains.automation.scheduler import WeeklyScheduler
from tests.test_weekly_outreach import _enable_weekly, _ready_lead, _template

SUNDAY = datetime(2026, 10, 18, 23, 50).astimezone()
MONDAY = datetime(2026, 10, 19, 0, 5).astimezone()


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _weekly_campaign(client: TestClient, campaign_payload: dict[str, object]) -> str:
    campaign = client.post("/api/v1/campaigns", json=campaign_payload).json()
    _ready_lead(client, campaign["id"])
    _enable_weekly(client, campaign["id"], _template(client)["id"])
    return str(campaign["id"])


def _weekly_runs(app: FastAPI) -> list[tuple[str, date | None]]:
    with app.state.database.session_factory() as session:
        return [
            (run.campaign_id, run.week_start)
            for run in session.query(CampaignRun).filter(CampaignRun.week_start.is_not(None))
        ]


def test_an_app_left_open_across_the_week_boundary_queues_the_new_week(
    client: TestClient, app: FastAPI, campaign_payload: dict[str, object]
) -> None:
    campaign_id = _weekly_campaign(client, campaign_payload)
    manager: CampaignRunManager = app.state.campaign_run_manager
    clock = _Clock(SUNDAY)
    scheduler = WeeklyScheduler(manager.queue_weekly_due, poll_seconds=900, clock=clock)

    scheduler.check_now()
    scheduler.check_now()
    sunday_week = SUNDAY.date() - timedelta(days=6)
    assert _weekly_runs(app) == [(campaign_id, sunday_week)]

    clock.now = MONDAY
    scheduler.check_now()
    assert sorted(_weekly_runs(app), key=lambda row: str(row[1])) == [
        (campaign_id, sunday_week),
        (campaign_id, MONDAY.date()),
    ]


def test_the_scheduler_thread_checks_at_start_and_survives_a_failing_check() -> None:
    calls: list[date] = []
    checked_twice = threading.Event()

    def queue(correlation_id: str, week_start: date) -> list[str]:
        calls.append(week_start)
        if len(calls) == 1:
            raise RuntimeError("database briefly locked")
        checked_twice.set()
        return []

    scheduler = WeeklyScheduler(queue, poll_seconds=0.05, clock=_Clock(MONDAY))
    scheduler.start()
    try:
        assert checked_twice.wait(timeout=5)
    finally:
        scheduler.stop()
    assert calls[:2] == [MONDAY.date(), MONDAY.date()]


def test_scheduler_and_endpoint_racing_create_one_run_per_campaign(
    client: TestClient, app: FastAPI, campaign_payload: dict[str, object]
) -> None:
    _weekly_campaign(client, campaign_payload)
    manager: CampaignRunManager = app.state.campaign_run_manager
    barrier = threading.Barrier(4)
    errors: list[BaseException] = []

    def check() -> None:
        try:
            barrier.wait()
            manager.queue_weekly_due("race")
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=check) for _ in range(3)]
    for thread in threads:
        thread.start()
    barrier.wait()
    response = client.post("/api/v1/campaign-runs/weekly/ensure")
    for thread in threads:
        thread.join()

    assert errors == []
    assert response.status_code == 200, response.text
    assert len(_weekly_runs(app)) == 1


def test_the_database_allows_one_weekly_run_per_campaign_per_week(app: FastAPI) -> None:
    """Added by migration 0011; the model declares it too so the two cannot drift apart."""
    with app.state.database.session_factory() as session:
        indexes = session.execute(text("PRAGMA index_list('campaign_run')")).all()
        unique_columns = [
            [column.name for column in session.execute(text(f"PRAGMA index_info('{row.name}')"))]
            for row in indexes
            if row.unique
        ]
    assert ["campaign_id", "week_start"] in unique_columns
