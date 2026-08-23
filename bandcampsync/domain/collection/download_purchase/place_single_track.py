import logging
from collections.abc import Callable
from pathlib import Path

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.collection.download_purchase.context import PurchaseDownloadContext
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome
from bandcampsync.domain.file_transfer import copy_file

log = logging.getLogger("sync")


def place_single_track(
    purchase: BandcampItem,
    ctx: PurchaseDownloadContext,
    temp_file_path: Path,
    media_format: str,
    local_path: Path,
    record_error: Callable[[str], None],
) -> PlacementOutcome:
    slug = purchase.item_title
    if purchase.url_hints and isinstance(purchase.url_hints, dict):
        slug = purchase.url_hints.get("slug", purchase.item_title)
    format_extension = ctx.local_media.clean_format(media_format)
    try:
        local_path.mkdir(parents=True, exist_ok=True)
    except OSError as mkdir_error:
        record_error(
            f"Failed to create directory: {local_path} ({mkdir_error}), skipping file write"
        )
        return PlacementOutcome.RETRY_ATTEMPT
    file_dest = ctx.local_media.get_path_for_file(local_path, f"{slug}.{format_extension}")
    log.info(f'Copying single track: "{temp_file_path}" to "{file_dest}"')
    try:
        copy_file(temp_file_path, file_dest)
    except OSError as copy_error:
        record_error(f"Failed to copy {temp_file_path} to {file_dest}: {copy_error}")
    return PlacementOutcome.PLACED
