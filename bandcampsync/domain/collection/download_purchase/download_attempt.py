import logging
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.collection.download_purchase.context import (
    PurchaseDownloadContext,
    PurchaseDownloadResult,
)
from bandcampsync.domain.collection.download_purchase.file_placement import place_downloaded_file
from bandcampsync.domain.collection.download_purchase.local_bookkeeping import (
    mark_purchase_downloaded,
)
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome
from bandcampsync.domain.file_transfer import mask_signed_url

log = logging.getLogger("sync")


class PlacementRetryNeeded(Exception):
    """Raised when placement failed for a reason worth retrying the whole
    download for (a local mkdir failure), rather than accepting or rejecting it.
    """


def attempt_download(
    purchase: BandcampItem,
    ctx: PurchaseDownloadContext,
    media_format: str,
    local_path: Path,
    record_error: Callable[[str], None],
) -> PurchaseDownloadResult:
    initial_download_url = ctx.bandcamp.get_download_file_url(purchase, encoding=media_format)
    download_file_url = ctx.bandcamp.check_download_stat(purchase, initial_download_url)

    with NamedTemporaryFile(mode="w+b", delete=True, dir=ctx.temp_dir_root) as temp_file:
        log.info(
            f'Downloading item "{purchase.band_name} / {purchase.item_title}" '
            f"(id:{purchase.item_id}) from {mask_signed_url(download_file_url)} "
            f"to {temp_file.name}"
        )
        download_content_type = ctx.bandcamp.fetch_purchase_file(download_file_url, temp_file)
        temp_file.seek(0)
        temp_file_path = Path(temp_file.name)

        placement_outcome = place_downloaded_file(
            purchase,
            ctx,
            temp_file_path,
            download_content_type,
            media_format,
            local_path,
            record_error,
        )
        if placement_outcome is PlacementOutcome.RETRY_ATTEMPT:
            raise PlacementRetryNeeded
        if placement_outcome is PlacementOutcome.UNRECOGNIZED_CONTENT:
            return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)

        mark_purchase_downloaded(purchase, ctx, local_path, record_error)
        return PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)
