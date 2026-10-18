"""Weekly outreach is scheduled by the backend while the app is running (FR-060, decision D5).

It used to run only when the frontend loaded and asked for it, so an app left open across the week
boundary never queued that week's runs. The check is idempotent: each enabled campaign gets at most
one run per week, so repeating it every interval only queues what is due, including a campaign
enabled part-way through the week, as opening the app always did.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import date, datetime
from uuid import uuid4

from app.domains.automation.weekly import current_week_start

logger = logging.getLogger(__name__)

QueueWeeklyDue = Callable[[str, date], list[str]]
Clock = Callable[[], datetime]


def _local_now() -> datetime:
    return datetime.now().astimezone()


class WeeklyScheduler:
    def __init__(
        self,
        queue_weekly_due: QueueWeeklyDue,
        *,
        poll_seconds: float,
        clock: Clock = _local_now,
    ) -> None:
        self._queue_weekly_due = queue_weekly_due
        self._poll_seconds = poll_seconds
        self._clock = clock
        self._week: date | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check_now(self) -> list[str]:
        """Queue every due campaign for the current week; returns this week's run IDs. The
        manager logs the runs it actually creates."""
        week = current_week_start(self._clock())
        if week != self._week:
            logger.info("Weekly outreach check for a new week", extra={"week_start": str(week)})
            self._week = week
        return self._queue_weekly_due(str(uuid4()), week)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        # The first check runs on the thread, so startup does not wait for it.
        self._thread = threading.Thread(target=self._run, name="weekly-scheduler", daemon=True)
        self._thread.start()
        logger.info("Weekly outreach scheduler started", extra={"poll_seconds": self._poll_seconds})

    def _run(self) -> None:
        while True:
            try:
                self.check_now()
            except Exception:
                logger.exception("Weekly outreach check failed; it will be retried")
            if self._stop.wait(self._poll_seconds):
                return

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
