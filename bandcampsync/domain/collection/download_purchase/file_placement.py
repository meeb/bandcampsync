from collections.abc import Callable
from pathlib import Path

from bandcampsync.domain.bandcamp import BandcampItem
from bandcampsync.domain.collection.download_purchase.context import PurchaseDownloadContext
from bandcampsync.domain.collection.download_purchase.place_single_track import (
    place_single_track,
)
from bandcampsync.domain.collection.download_purchase.place_zip_archive import place_zip_archive
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome
from bandcampsync.domain.file_transfer import is_zip_archive


def is_single_track(purchase: BandcampItem, download_content_type: str) -> bool:
    return (
        purchase.item_type == "track"
        or download_content_type.startswith("audio/")
        # Bandcamp may serve Ogg Vorbis as application/ogg.
        or download_content_type == "application/ogg"
    )


def place_downloaded_file(
    purchase: BandcampItem,
    ctx: PurchaseDownloadContext,
    temp_file_path: Path,
    download_content_type: str,
    media_format: str,
    local_path: Path,
    record_error: Callable[[str], None],
) -> PlacementOutcome:
    if is_zip_archive(temp_file_path):
        return place_zip_archive(ctx, temp_file_path, local_path, record_error)
    if is_single_track(purchase, download_content_type):
        return place_single_track(
            purchase, ctx, temp_file_path, media_format, local_path, record_error
        )
    record_error(
        f'Downloaded file for "{purchase.band_name} / {purchase.item_title}" '
        f'(id:{purchase.item_id}) at "{temp_file_path}" is not a zip '
        f"archive or a single track, skipping"
    )
    return PlacementOutcome.UNRECOGNIZED_CONTENT
