"""Pure logic and low-level mechanics for the sync service: Bandcamp domain
types and contracts (domain.bandcamp - the client itself lives in
interface.bandcamp), download primitives (domain.download), local media
indexing, ignore-list handling, collection sync mechanics (domain.sync),
scheduling math, and run-state tracking.

Import order below is dependency order, not alphabetical: bandcamp depends on
download; ignores/media depend on bandcamp; domain.sync depends on all of
those, so it loads last.
"""

from bandcampsync.domain import logging_setup  # noqa: I001
from bandcampsync.domain.constants import INTERNAL_USER_AGENT, VERSION
from bandcampsync.domain.download import (
    DownloadBadStatusCode,
    DownloadExpired,
    DownloadInvalidContentType,
    copy_file,
    download_file,
    is_zip_file,
    mask_sig,
    move_file,
    unzip_file,
)
from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.domain.scheduling import LogTail, SyncState, compute_next_run
from bandcampsync.domain.bandcamp import (
    BandcampDownloadUnavailable,
    BandcampError,
    BandcampItem,
    BandcampSession,
)
from bandcampsync.domain.ignores import Ignores
from bandcampsync.domain.media import LocalMedia
from bandcampsync.domain.notify import NotifyURL
from bandcampsync.domain.sync import (
    ItemSyncContext,
    ItemSyncResult,
    PurchaseDateParser,
    SyncOutcome,
    item_token,
    load_checkpoint,
    ordered_purchases,
    resolve_checkpoint_candidate,
    save_checkpoint,
    select_items_to_sync,
    should_stop_loading_purchase,
    sync_item,
)

__all__ = [
    "INTERNAL_USER_AGENT",
    "VERSION",
    "BandcampDownloadUnavailable",
    "BandcampError",
    "BandcampItem",
    "BandcampSession",
    "BandcampSyncOptions",
    "DownloadBadStatusCode",
    "DownloadExpired",
    "DownloadInvalidContentType",
    "Ignores",
    "ItemSyncContext",
    "ItemSyncResult",
    "LocalMedia",
    "LogTail",
    "NotifyURL",
    "PurchaseDateParser",
    "SyncOutcome",
    "SyncState",
    "compute_next_run",
    "copy_file",
    "download_file",
    "is_zip_file",
    "item_token",
    "load_checkpoint",
    "logging_setup",
    "mask_sig",
    "move_file",
    "ordered_purchases",
    "resolve_checkpoint_candidate",
    "save_checkpoint",
    "select_items_to_sync",
    "should_stop_loading_purchase",
    "sync_item",
    "unzip_file",
]
