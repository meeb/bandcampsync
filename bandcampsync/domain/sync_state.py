"""Shared, lock-protected view of what the sync service is doing."""

import threading
from datetime import datetime, timezone


class SyncState:
    """Read by the HTTP interface, written by the service loop. Kept separate
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
