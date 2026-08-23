"""Orchestrates a full collection sync: composes the domain pieces and the
outbound Bandcamp client (interface.bandcamp) into the "sync my collection"
use case - authenticate, decide what's missing, sync it, remember where we
got to, notify.
"""

import asyncio

from bandcampsync.domain.collection import (
    PurchaseDateParser,
    PurchaseDownloadContext,
    PurchaseDownloadResult,
    SyncOutcome,
    load_checkpoint,
    select_items_to_sync,
    should_stop_loading_purchase,
)
from bandcampsync.domain.ignores import Ignores
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.domain.media import LocalMedia
from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.interface.bandcamp import Bandcamp
from bandcampsync.service.log_id_file_migration_warning import (
    log_id_file_migration_warning_if_needed,
)
from bandcampsync.service.log_sync_error_summary import log_sync_error_summary
from bandcampsync.service.maybe_notify import maybe_notify
from bandcampsync.service.maybe_save_checkpoint import maybe_save_checkpoint
from bandcampsync.service.sync_all_items import sync_all_items

log = get_logger("sync")


def sync_collection(options: BandcampSyncOptions) -> SyncOutcome:
    """Runs one full collection sync and returns what happened."""
    ignores = Ignores(ign_file_path=options.ign_file_path, ign_patterns=options.ign_patterns)
    dry_run = bool(options.dry_run)
    concurrency = max(1, options.concurrency)
    date_parser = PurchaseDateParser()

    use_collection_checkpoint = not options.until_date
    checkpoint_token = load_checkpoint(options.dir_path) if use_collection_checkpoint else None
    index_local_media = not checkpoint_token
    if not index_local_media:
        log.info("Collection checkpoint loaded; skipping initial local media index")
    local_media = LocalMedia(
        media_dir=options.dir_path,
        ignores=ignores,
        skip_item_index=options.skip_item_index,
        sync_ignore_file=options.sync_ignore_file,
        index_on_init=index_local_media,
    )

    bandcamp = Bandcamp(cookies=options.cookies)
    bandcamp.verify_authentication()
    bandcamp.load_purchases(
        stop_when=lambda item: should_stop_loading_purchase(
            item, date_parser, checkpoint_token, options.until_date
        )
    )

    if options.until_date:
        log.info(
            "Will stop after processing purchases on or after: "
            f"{options.until_date.isoformat()} (purchase date GMT)"
        )
    if dry_run:
        log.info("Dry run enabled: will not download or write files")

    ctx = PurchaseDownloadContext(
        bandcamp=bandcamp,
        local_media=local_media,
        ignores=ignores,
        media_format=options.media_format,
        temp_dir_root=options.temp_dir_root,
        max_retries=max(1, options.max_retries),
        retry_wait=max(0, options.retry_wait),
        dry_run=dry_run,
        skip_hidden=options.skip_hidden,
        ign_file_path=options.ign_file_path,
    )

    errors: list[str] = []

    def record_error(message: str) -> None:
        errors.append(message)
        log.error(message)

    items = select_items_to_sync(
        bandcamp.purchases, date_parser, checkpoint_token, options.until_date
    )
    results: list[PurchaseDownloadResult] = []
    if not items:
        log.info("No purchases to sync after applying filters")
    else:
        results = asyncio.run(sync_all_items(items, ctx, record_error, concurrency))

    new_items_downloaded = any(r.downloaded for r in results)
    show_id_file_warning = any(r.show_id_file_warning for r in results)

    log_id_file_migration_warning_if_needed(
        show_id_file_warning, options.sync_ignore_file, options.ign_file_path
    )
    log_sync_error_summary(errors)
    maybe_save_checkpoint(
        options.dir_path,
        use_collection_checkpoint,
        dry_run,
        bool(errors),
        bandcamp.purchases,
        bandcamp.collection_items,
    )
    maybe_notify(dry_run, new_items_downloaded, options.notify_url)

    return SyncOutcome(new_items_downloaded=new_items_downloaded, errors=errors)
