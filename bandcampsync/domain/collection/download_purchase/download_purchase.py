import logging
import time
from collections.abc import Callable

from bandcampsync.domain.bandcamp import (
    BandcampDownloadExpired,
    BandcampDownloadUnavailable,
    BandcampError,
    BandcampItem,
)
from bandcampsync.domain.collection.download_purchase.context import (
    PurchaseDownloadContext,
    PurchaseDownloadResult,
)
from bandcampsync.domain.collection.download_purchase.download_attempt import (
    PlacementRetryNeeded,
    attempt_download,
)
from bandcampsync.domain.collection.download_purchase.skip_rules import find_skip_reason
from bandcampsync.domain.file_transfer import TransferBadStatusCode

log = logging.getLogger("sync")


def download_purchase(
    purchase: BandcampItem,
    ctx: PurchaseDownloadContext,
    record_error: Callable[[str], None],
    encoding: str | None = None,
) -> PurchaseDownloadResult:
    media_format = encoding or ctx.media_format
    local_path = ctx.local_media.get_path_for_purchase(purchase)

    skip_result = find_skip_reason(purchase, ctx, local_path)
    if skip_result is not None:
        return skip_result

    log.info(
        f'New media item, will download: "{purchase.band_name} / {purchase.item_title}" '
        f'(id:{purchase.item_id}) in "{media_format}"'
    )
    if ctx.dry_run:
        log.info(
            f'DRY RUN: would download "{purchase.band_name} / {purchase.item_title}" '
            f"(id:{purchase.item_id})"
        )
        return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)

    for attempt in range(ctx.max_retries):
        try:
            return attempt_download(purchase, ctx, media_format, local_path, record_error)
        except PlacementRetryNeeded:  # noqa: PERF203
            continue
        except BandcampDownloadUnavailable as unavailable_error:
            log.info(
                f'No download available for "{purchase.band_name} / {purchase.item_title}" '
                f"(id:{purchase.item_id}): {unavailable_error}. Skipping."
            )
            return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)
        except BandcampDownloadExpired:
            # Must be caught before the BandcampError clause below (it's a
            # subclass): unlike other BandcampErrors, this one doesn't retry.
            record_error(
                f"Download expired and requires email confirmation on Bandcamp for "
                f'"{purchase.band_name} / {purchase.item_title}" (id:{purchase.item_id}), '
                f"skipping"
            )
            return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)
        except (BandcampError, TransferBadStatusCode) as download_error:
            if attempt < ctx.max_retries - 1:
                log.warning(
                    f"Attempt {attempt + 1} failed for {purchase.band_name} / "
                    f"{purchase.item_title}: {download_error}. Retrying in "
                    f"{ctx.retry_wait} seconds..."
                )
                time.sleep(ctx.retry_wait)
                continue
            record_error(
                f"All {ctx.max_retries} attempts failed for {purchase.band_name} / "
                f"{purchase.item_title}: {download_error}. Skipping."
            )
            return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)
    return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)
