"""Public API surface, stable across the domain/service/interface reorganisation
underneath - bin/bandcampsync and external consumers import from here, not
from the submodules directly.
"""

from bandcampsync.domain import logging_setup as logger
from bandcampsync.domain.collection import SyncOutcome
from bandcampsync.domain.constants import (
    VERSION as version,  # noqa: N811 - bin/bandcampsync prints this lowercase
)
from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.service.do_sync import do_sync
from bandcampsync.service.sync_collection import sync_collection

__all__ = [
    "BandcampSyncOptions",
    "SyncOutcome",
    "do_sync",
    "logger",
    "sync_collection",
    "version",
]
