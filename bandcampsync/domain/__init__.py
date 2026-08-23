"""Scheduling and logging surface shared by the service and interface layers.

Deliberately not a everything-barrel for the rest of domain: every other
domain submodule (bandcamp, file_transfer, collection, media, ignores,
options, notify) is small and specific enough that callers import it
directly, which also means renaming one doesn't require updating a giant
__all__ here. This file exists only for the pieces genuinely shared across
layers: the console log format (logging_setup), and the service loop's
run-state tracking and schedule math (scheduling).
"""

from bandcampsync.domain import logging_setup
from bandcampsync.domain.scheduling import LogTail, SyncState, compute_next_run

__all__ = [
    "LogTail",
    "SyncState",
    "compute_next_run",
    "logging_setup",
]
