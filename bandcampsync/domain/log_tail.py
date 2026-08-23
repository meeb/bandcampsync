"""In-memory log ring buffer for the sync service's status page."""

import logging
import threading
from collections import deque


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
