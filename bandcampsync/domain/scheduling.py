"""Scheduling math and run-state tracking for the sync service loop.

compute_next_run is pulled out as a pure function (no clock access, no
randomness of its own) specifically so the daily-schedule math is testable
without waiting on a real day boundary or mocking datetime.now.
"""

import logging
import threading
from collections import deque
from datetime import datetime, timedelta, timezone


def compute_next_run(now: datetime, run_daily_at: int, random_delay: int) -> tuple[datetime, int]:
    """Compute the next scheduled run time and how many seconds until then.

    Args:
        now: Current time, timezone-aware, in the target timezone.
        run_daily_at: Hour of day (0-23) the daily run should land on.
        random_delay: Extra seconds of jitter to add on top of the hour boundary.

    Returns:
        (next_run, sleep_seconds) - next_run is tomorrow at run_daily_at:00:00,
        sleep_seconds is the whole-second gap between now and next_run plus jitter.
    """
    next_run = now.replace(hour=run_daily_at, minute=0, second=0, microsecond=0)
    next_run += timedelta(days=1)
    sleep_seconds = int((next_run - now).total_seconds() + random_delay)
    return next_run, sleep_seconds


class SyncState:
    """Shared, lock-protected view of what the service is doing.

    Read by the HTTP interface, written by the service loop. Kept separate
    from the loop itself so the HTTP layer never touches Syncer/do_sync
    directly - it only ever asks for a sync via the wake event and reports
    on whatever the loop last told it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.status = "idle"  # idle | running
        self.last_run_started: str | None = None
        self.last_run_finished: str | None = None
        self.last_result: str | None = None
        self.next_scheduled: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        with self._lock:
            return {
                "status": self.status,
                "last_run_started": self.last_run_started,
                "last_run_finished": self.last_run_finished,
                "last_result": self.last_result,
                "next_scheduled": self.next_scheduled,
            }

    def mark_running(self) -> None:
        with self._lock:
            self.status = "running"
            self.last_run_started = datetime.now(timezone.utc).isoformat()

    def mark_finished(self, result: str, next_scheduled: str | None = None) -> None:
        with self._lock:
            self.status = "idle"
            self.last_run_finished = datetime.now(timezone.utc).isoformat()
            self.last_result = result
            if next_scheduled is not None:
                self.next_scheduled = next_scheduled


class LogTail(logging.Handler):
    """Keeps the last N formatted log lines in memory for the status page."""

    def __init__(self, capacity: int = 200) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter("%(asctime)s %(name)s [%(levelname)s] %(message)s"))
        self._lines: deque[str] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        with self._lock:
            self._lines.append(line)

    def tail(self) -> list[str]:
        with self._lock:
            return list(self._lines)
