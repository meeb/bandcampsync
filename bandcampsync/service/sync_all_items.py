"""Runs download_purchase over a batch of purchases, sequentially or with
bounded concurrency.
"""

import asyncio
import logging
from collections.abc import Callable

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.collection import (
    PurchaseDownloadContext,
    PurchaseDownloadResult,
    download_purchase,
)

logger = logging.getLogger("sync")


async def sync_all_items(
    items: list[BandcampItem],
    ctx: PurchaseDownloadContext,
    record_error: Callable[[str], None],
    concurrency: int,
) -> list[PurchaseDownloadResult]:
    total = len(items)
    if concurrency == 1:
        sequential_results: list[PurchaseDownloadResult] = []
        for i, item in enumerate(items, 1):
            percent = (i / total) * 100 if total else 0
            logger.info(f"Syncing item {i} of {total} ({percent:.1f}%)")
            sequential_results.append(download_purchase(item, ctx, record_error))
        return sequential_results

    # Concurrent processing with a semaphore to limit concurrency. download_purchase
    # is blocking I/O, so it runs in a thread pool executor rather than directly
    # on the event loop.
    semaphore = asyncio.Semaphore(concurrency)
    concurrent_results: list[PurchaseDownloadResult | None] = [None] * total

    async def sync_with_semaphore(index: int, item: BandcampItem) -> None:
        async with semaphore:
            loop = asyncio.get_event_loop()
            concurrent_results[index] = await loop.run_in_executor(
                None, download_purchase, item, ctx, record_error
            )

    logger.info(f"Syncing {total} items with concurrency {concurrency}")
    await asyncio.gather(*(sync_with_semaphore(i, item) for i, item in enumerate(items)))
    return [r for r in concurrent_results if r is not None]
