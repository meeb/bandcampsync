"""LocalMedia: a thin, stateful session over one sync run's local media
directory. The substantive logic (path computation, directory-walk
indexing, the locally-downloaded check, writing the id marker file) lives
in domain/local_media_entry/ as plain functions - this class exists only
to hold the live, mutable working index across the run (is_locally_downloaded
lazily discovers and caches new entries as purchases are processed
concurrently; see local_media_entry/checks.py for why that stays a plain
mutable dict/set rather than an immutable snapshot rebuilt on every call).
"""

from pathlib import Path

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.ignore_entry import IgnoreFileWriter, IgnoreRules, is_ignored
from bandcampsync.domain.local_media_entry import (
    ITEM_INDEX_FILENAME as _ITEM_INDEX_FILENAME,
)
from bandcampsync.domain.local_media_entry import (
    clean_format,
    index_local_media,
    is_locally_downloaded,
    path_for_file,
    path_for_purchase,
    write_bandcamp_id,
)
from bandcampsync.domain.logging_setup import get_logger

log = get_logger("media")


class LocalMedia:
    """A local media directory indexer. This stores media in the following format:

    /media_dir/
    /media_dir/Artist Name
    /media_dir/Artist Name/Album Name
    /media_dir/Artist Name/Album Name/bandcamp_item_id.txt
    /media_dir/Artist Name/Album Name/track1.flac
    /media_dir/Artist Name/Album Name/track2.flac
    """

    ITEM_INDEX_FILENAME = _ITEM_INDEX_FILENAME

    def __init__(
        self,
        media_dir: Path,
        ignore_rules: IgnoreRules,
        ignore_file_writer: IgnoreFileWriter,
        skip_item_index: bool,
        sync_ignore_file: bool,
        index_on_init: bool = True,
    ) -> None:
        self.media_dir = media_dir
        self.media: dict[int, Path] = {}
        self.item_names: set[tuple[str, str]] = set()
        log.info(f"Local media directory: {self.media_dir}")

        def on_item_discovered(item_id: int, band_name: str, item_title: str) -> None:
            if not sync_ignore_file:
                return
            item = BandcampItem(item_id=item_id, band_name=band_name, item_title=item_title)
            if not is_ignored(ignore_rules, item):
                ignore_file_writer.record(item)

        # If the "ignores" file is empty, we need to traverse the filesystem anyway
        if index_on_init and (not skip_item_index or len(ignore_rules.ids) < 1):
            snapshot = index_local_media(media_dir, on_item_discovered=on_item_discovered)
            self.media = dict(snapshot.by_item_id)
            self.item_names = set(snapshot.item_names)

    @staticmethod
    def clean_format(format_str: str) -> str:
        return clean_format(format_str)

    def is_locally_downloaded(self, item: BandcampItem, local_path: Path) -> bool:
        return is_locally_downloaded(self.media, self.item_names, item, local_path)

    def get_path_for_purchase(self, item: BandcampItem) -> Path:
        return path_for_purchase(self.media_dir, item)

    def get_path_for_file(self, local_path: Path, file_name: str) -> Path:
        return path_for_file(local_path, file_name)

    def write_bandcamp_id(self, item: BandcampItem, dirpath: Path) -> bool:
        return write_bandcamp_id(item, dirpath)
