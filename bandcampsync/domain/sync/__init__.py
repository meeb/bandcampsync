"""Everything involved in syncing a Bandcamp collection to local disk except
the top-level orchestration (that's service/sync_collection.py): the
checkpoint file, deciding which purchases to sync and in what order, and
syncing a single item.

All three submodules share the "sync" logger by name (via plain
logging.getLogger, not the get_logger() wrapper) - the wrapper is only
called once, in service/sync_collection.py, to configure it. Calling it
again here would attach a second handler and double every log line.
"""

from bandcampsync.domain.sync.checkpoint import (
    load_checkpoint,
    resolve_checkpoint_candidate,
    save_checkpoint,
)
from bandcampsync.domain.sync.item import ItemSyncContext, ItemSyncResult, sync_item
from bandcampsync.domain.sync.outcome import SyncOutcome
from bandcampsync.domain.sync.selection import (
    PurchaseDateParser,
    item_token,
    ordered_purchases,
    select_items_to_sync,
    should_stop_loading_purchase,
)

__all__ = [
    "ItemSyncContext",
    "ItemSyncResult",
    "PurchaseDateParser",
    "SyncOutcome",
    "item_token",
    "load_checkpoint",
    "ordered_purchases",
    "resolve_checkpoint_candidate",
    "save_checkpoint",
    "select_items_to_sync",
    "should_stop_loading_purchase",
    "sync_item",
]
