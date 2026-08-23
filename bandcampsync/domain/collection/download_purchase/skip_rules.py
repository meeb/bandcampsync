import logging
from pathlib import Path

from bandcampsync.domain.bandcamp import BandcampItem
from bandcampsync.domain.collection.download_purchase.context import (
    PurchaseDownloadContext,
    PurchaseDownloadResult,
)

log = logging.getLogger("sync")


def find_skip_reason(
    purchase: BandcampItem, ctx: PurchaseDownloadContext, local_path: Path
) -> PurchaseDownloadResult | None:
    """Returns a result to short-circuit on, or None if the purchase should
    go on to be downloaded.
    """
    if ctx.skip_hidden and purchase.hidden:
        log.info(
            f'Item is hidden, skipping: "{purchase.band_name} / {purchase.item_title}" '
            f"(id:{purchase.item_id})"
        )
        return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)

    if ctx.ignores.is_ignored(purchase):
        show_id_file_warning = ctx.local_media.is_locally_downloaded(purchase, local_path)
        return PurchaseDownloadResult(downloaded=False, show_id_file_warning=show_id_file_warning)

    if purchase.is_preorder:
        log.info(
            f'Item is a preorder, skipping: "{purchase.band_name} / {purchase.item_title}" '
            f"(id:{purchase.item_id})"
        )
        return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)

    if ctx.local_media.is_locally_downloaded(purchase, local_path):
        log.info(
            f'Already locally downloaded, skipping: "{purchase.band_name} / '
            f'{purchase.item_title}" (id:{purchase.item_id})'
        )
        return PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)

    return None
