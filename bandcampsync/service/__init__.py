"""Orchestrates the use cases: a full collection sync, and the scheduled service
loop (scheduling, wake-on-demand, state updates) that runs it.
"""

from bandcampsync.service.authenticate_and_load_collection import authenticate_and_load_collection
from bandcampsync.service.do_sync import do_sync
from bandcampsync.service.log_id_file_migration_warning import (
    log_id_file_migration_warning_if_needed,
)
from bandcampsync.service.log_sync_error_summary import log_sync_error_summary
from bandcampsync.service.maybe_notify import maybe_notify
from bandcampsync.service.maybe_save_checkpoint import maybe_save_checkpoint
from bandcampsync.service.prepare_local_media import prepare_local_media
from bandcampsync.service.run_scheduled_sync import run_scheduled_sync, run_scheduled_sync_with
from bandcampsync.service.sync_all_items import sync_all_items
from bandcampsync.service.sync_collection import sync_collection, sync_collection_with

__all__ = [
    "authenticate_and_load_collection",
    "do_sync",
    "log_id_file_migration_warning_if_needed",
    "log_sync_error_summary",
    "maybe_notify",
    "maybe_save_checkpoint",
    "prepare_local_media",
    "run_scheduled_sync",
    "run_scheduled_sync_with",
    "sync_all_items",
    "sync_collection",
    "sync_collection_with",
]
