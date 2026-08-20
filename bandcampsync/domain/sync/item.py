"""Downloads and files a single purchased item: retries transient failures,
extracts a downloaded zip or copies a single track into place, and records
what's now locally downloaded.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from bandcampsync.domain.bandcamp import (
    BandcampDownloadUnavailable,
    BandcampError,
    BandcampItem,
    BandcampSession,
)
from bandcampsync.domain.download import (
    DownloadBadStatusCode,
    DownloadExpired,
    DownloadInvalidContentType,
    copy_file,
    download_file,
    is_zip_file,
    mask_sig,
    move_file,
    unzip_file,
)
from bandcampsync.domain.ignores import Ignores
from bandcampsync.domain.media import LocalMedia

log = logging.getLogger("sync")


@dataclass(frozen=True)
class ItemSyncContext:
    """Dependencies and settings shared across every item synced in one run."""

    bandcamp: BandcampSession
    local_media: LocalMedia
    ignores: Ignores
    media_format: str
    temp_dir_root: Path | None
    max_retries: int
    retry_wait: int
    dry_run: bool
    skip_hidden: bool
    ign_file_path: Path | None


@dataclass(frozen=True)
class ItemSyncResult:
    downloaded: bool
    # True if this item is locally downloaded only via the legacy
    # per-directory bandcamp_item_id.txt file, not the shared ignore file.
    show_id_file_warning: bool


def sync_item(
    item: BandcampItem,
    ctx: ItemSyncContext,
    record_error: Callable[[str], None],
    encoding: str | None = None,
) -> ItemSyncResult:
    """Syncs a single item (purchase)."""
    media_format = encoding or ctx.media_format

    local_path = ctx.local_media.get_path_for_purchase(item)

    if ctx.skip_hidden and item.hidden:
        log.info(
            f'Item is hidden, skipping: "{item.band_name} / {item.item_title}" (id:{item.item_id})'
        )
        return ItemSyncResult(downloaded=False, show_id_file_warning=False)

    if ctx.ignores.is_ignored(item):
        show_id_file_warning = ctx.local_media.is_locally_downloaded(item, local_path)
        return ItemSyncResult(downloaded=False, show_id_file_warning=show_id_file_warning)

    if item.is_preorder:
        log.info(
            f'Item is a preorder, skipping: "{item.band_name} / {item.item_title}" '
            f"(id:{item.item_id})"
        )
        return ItemSyncResult(downloaded=False, show_id_file_warning=False)

    if ctx.local_media.is_locally_downloaded(item, local_path):
        log.info(
            f'Already locally downloaded, skipping: "{item.band_name} / {item.item_title}" '
            f"(id:{item.item_id})"
        )
        return ItemSyncResult(downloaded=False, show_id_file_warning=False)

    log.info(
        f'New media item, will download: "{item.band_name} / {item.item_title}" '
        f'(id:{item.item_id}) in "{media_format}"'
    )
    if ctx.dry_run:
        log.info(
            f'DRY RUN: would download "{item.band_name} / {item.item_title}" (id:{item.item_id})'
        )
        return ItemSyncResult(downloaded=False, show_id_file_warning=False)

    for attempt in range(ctx.max_retries):
        try:
            initial_download_url = ctx.bandcamp.get_download_file_url(item, encoding=media_format)
            download_file_url = ctx.bandcamp.check_download_stat(item, initial_download_url)

            with NamedTemporaryFile(mode="w+b", delete=True, dir=ctx.temp_dir_root) as temp_file:
                log.info(
                    f'Downloading item "{item.band_name} / {item.item_title}" '
                    f"(id:{item.item_id}) from {mask_sig(download_file_url)} "
                    f"to {temp_file.name}"
                )
                download_content_type = download_file(download_file_url, temp_file)
                temp_file.seek(0)
                temp_file_path = Path(temp_file.name)
                if is_zip_file(temp_file_path):
                    with TemporaryDirectory(dir=ctx.temp_dir_root) as temp_dir:
                        log.info(f'Decompressing downloaded zip "{temp_file.name}" to "{temp_dir}"')
                        unzip_file(Path(temp_file.name), Path(temp_dir))
                        temp_path = Path(temp_dir)
                        try:
                            local_path.mkdir(parents=True, exist_ok=True)
                        except OSError as e:
                            record_error(
                                f"Failed to create directory: {local_path} "
                                f"({e}), skipping file extraction"
                            )
                            continue
                        for file_path in temp_path.iterdir():
                            file_dest = ctx.local_media.get_path_for_file(
                                local_path, file_path.name
                            )
                            log.info(f'Moving extracted file: "{file_path}" to "{file_dest}"')
                            try:
                                move_file(file_path, file_dest)
                            except OSError as e:
                                record_error(f"Failed to move {file_path} to {file_dest}: {e}")
                elif (
                    item.item_type == "track"
                    or download_content_type.startswith("audio/")
                    # Bandcamp may serve Ogg Vorbis as application/ogg.
                    or download_content_type == "application/ogg"
                ):
                    slug = item.item_title
                    if item.url_hints and isinstance(item.url_hints, dict):
                        slug = item.url_hints.get("slug", item.item_title)
                    format_extension = ctx.local_media.clean_format(media_format)
                    try:
                        local_path.mkdir(parents=True, exist_ok=True)
                    except OSError as e:
                        record_error(
                            f"Failed to create directory: {local_path} ({e}), skipping file write"
                        )
                        continue
                    file_dest = ctx.local_media.get_path_for_file(
                        local_path, f"{slug}.{format_extension}"
                    )
                    log.info(f'Copying single track: "{temp_file_path}" to "{file_dest}"')
                    try:
                        copy_file(temp_file_path, file_dest)
                    except OSError as e:
                        record_error(f"Failed to copy {temp_file_path} to {file_dest}: {e}")
                else:
                    record_error(
                        f'Downloaded file for "{item.band_name} / {item.item_title}" '
                        f'(id:{item.item_id}) at "{temp_file_path}" is not a zip '
                        f"archive or a single track, skipping"
                    )
                    return ItemSyncResult(downloaded=False, show_id_file_warning=False)

                if ctx.ign_file_path:
                    # We assume that if you use an "ignore" file once, you'll
                    # keep using it forever (e.g. Docker).
                    # If you don't, you'll get a warning for the missing ID file
                    # on the items downloaded in the current session.
                    ctx.ignores.add(item)
                else:
                    try:
                        ctx.local_media.write_bandcamp_id(item, local_path)
                    except (OSError, ValueError) as e:
                        record_error(
                            f"Failed to write bandcamp item id for "
                            f'"{item.band_name} / {item.item_title}" '
                            f'(id:{item.item_id}) to "{local_path}": {e}'
                        )

                return ItemSyncResult(downloaded=True, show_id_file_warning=False)

        except BandcampDownloadUnavailable as e:
            log.info(
                f'No download available for "{item.band_name} / {item.item_title}" '
                f"(id:{item.item_id}): {e}. Skipping."
            )
            return ItemSyncResult(downloaded=False, show_id_file_warning=False)
        except (
            BandcampError,
            DownloadBadStatusCode,
            DownloadInvalidContentType,
        ) as e:
            if attempt < ctx.max_retries - 1:
                log.warning(
                    f"Attempt {attempt + 1} failed for {item.band_name} / "
                    f"{item.item_title}: {e}. Retrying in {ctx.retry_wait} seconds..."
                )
                time.sleep(ctx.retry_wait)
                continue
            else:
                record_error(
                    f"All {ctx.max_retries} attempts failed for {item.band_name} / "
                    f"{item.item_title}: {e}. Skipping."
                )
                return ItemSyncResult(downloaded=False, show_id_file_warning=False)
        except DownloadExpired:
            record_error(
                f"Download expired and requires email confirmation on Bandcamp for "
                f'"{item.band_name} / {item.item_title}" (id:{item.item_id}), skipping'
            )
            return ItemSyncResult(downloaded=False, show_id_file_warning=False)
    return ItemSyncResult(downloaded=False, show_id_file_warning=False)
