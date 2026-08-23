import logging
from collections.abc import Callable
from pathlib import Path

from bandcampsync.domain.bandcamp import BandcampItem
from bandcampsync.domain.collection.download_purchase.context import PurchaseDownloadContext

log = logging.getLogger("sync")


def mark_purchase_downloaded(
    purchase: BandcampItem,
    ctx: PurchaseDownloadContext,
    local_path: Path,
    record_error: Callable[[str], None],
) -> None:
    if ctx.ign_file_path:
        # We assume that if you use an "ignore" file once, you'll keep using it
        # forever (e.g. Docker). If you don't, you'll get a warning for the
        # missing ID file on the purchases downloaded in the current session.
        ctx.ignores.add(purchase)
        return
    try:
        ctx.local_media.write_bandcamp_id(purchase, local_path)
    except (OSError, ValueError) as write_error:
        record_error(
            f"Failed to write bandcamp item id for "
            f'"{purchase.band_name} / {purchase.item_title}" '
            f'(id:{purchase.item_id}) to "{local_path}": {write_error}'
        )
