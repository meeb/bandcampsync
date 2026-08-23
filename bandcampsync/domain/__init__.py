"""Shared surface used by the service and interface layers.

Deliberately not a everything-barrel for the rest of domain: every other
domain submodule (bandcamp, file_transfer, collection, media, ignores,
options, notify) is small and specific enough that callers import it
directly, which also means renaming one doesn't require updating a giant
__all__ here. This file exists only for the pieces genuinely shared across
layers: the console log format (logging_setup), the service loop's schedule
math (scheduling), its run-state tracker (sync_state), and its in-memory
log tail (log_tail).
"""

from bandcampsync.domain import logging_setup
from bandcampsync.domain.log_tail import LogTail
from bandcampsync.domain.scheduling import compute_next_run
from bandcampsync.domain.sync_state import SyncState

__all__ = [
    "LogTail",
    "SyncState",
    "compute_next_run",
    "logging_setup",
]
