"""The fan's Bandcamp collection: which purchases need downloading and in
what order, checkpointing progress through it, and downloading one purchase.

All submodules share the "sync" logger by name (via plain logging.getLogger,
not the get_logger() wrapper) - the wrapper is only called once, in
service/sync_collection.py, to configure it. Calling it again here would
attach a second handler and double every log line.
"""

from bandcampsync.domain.collection.checkpoint import (
    load_checkpoint,
    resolve_checkpoint_candidate,
    save_checkpoint,
)
from bandcampsync.domain.collection.download_purchase import (
    PurchaseDownloadContext,
    PurchaseDownloadResult,
    download_purchase,
)
from bandcampsync.domain.collection.purchase_selection import (
    PurchaseDateParser,
    item_token,
    ordered_purchases,
    select_items_to_sync,
    should_stop_loading_purchase,
)
from bandcampsync.domain.collection.sync_outcome import SyncOutcome

__all__ = [
    "PurchaseDateParser",
    "PurchaseDownloadContext",
    "PurchaseDownloadResult",
    "SyncOutcome",
    "download_purchase",
    "item_token",
    "load_checkpoint",
    "ordered_purchases",
    "resolve_checkpoint_candidate",
    "save_checkpoint",
    "select_items_to_sync",
    "should_stop_loading_purchase",
]
