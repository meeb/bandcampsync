from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast
from unicodedata import normalize

from bandcampsync.domain.bandcamp import BandcampItem
from bandcampsync.domain.ignores import Ignores
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

    ITEM_INDEX_FILENAME = "bandcamp_item_id.txt"

    def __init__(
        self,
        media_dir: Path,
        ignores: Ignores,
        skip_item_index: bool,
        sync_ignore_file: bool,
        index_on_init: bool = True,
    ) -> None:
        self.media_dir = media_dir
        self.ignores = ignores
        self.media: dict[int, Path] = {}
        self.item_names: set[tuple[str, str]] = set()
        self.sync_ignore_file = sync_ignore_file
        log.info(f"Local media directory: {self.media_dir}")

        # If the "ignores" file is empty, we need to traverse the filesystem anyway
        if index_on_init and (not skip_item_index or len(self.ignores.ids) < 1):
            self.index()

    @staticmethod
    def _clean_path(path_str: str) -> str:
        path_str = str(path_str)
        disallowed_punctuation = "\"#%'*/?\\`:"
        normalized_path = normalize("NFKD", path_str)
        outstr = ""
        for c in normalized_path:
            if c not in disallowed_punctuation:
                outstr += c
        return outstr

    @staticmethod
    def clean_format(format_str: str) -> str:
        if "-" not in format_str:
            return format_str
        format_parts = format_str.split("-")
        format_prefix = format_parts[0]
        return format_prefix if format_prefix else format_str

    def index(self) -> bool:
        for child1 in self.media_dir.iterdir():
            if child1.is_dir():
                for child2 in child1.iterdir():
                    if child2.is_dir():
                        for child3 in child2.iterdir():
                            if child3.name == self.ITEM_INDEX_FILENAME:
                                self.item_names.add((child2.parent.name, child2.name))
                                try:
                                    item_id = self.read_item_id(child3)
                                except ValueError as e:
                                    log.warning(f"Skipping invalid item index file {child3}: {e}")
                                    continue
                                if self.sync_ignore_file:
                                    item = BandcampItem(
                                        {
                                            "item_id": item_id,
                                            "band_name": child2.parent.name,
                                            "item_title": child2.name,
                                        }
                                    )
                                    if not self.ignores.is_ignored(item):
                                        self.ignores.add(item)
                                self.media[item_id] = child2
                                log.info(f"Detected locally downloaded media: {item_id} = {child2}")
        return True

    @staticmethod
    def read_item_id(filepath: Path) -> int:
        with filepath.open() as f:
            item_id = f.read().strip()
        try:
            return int(item_id)
        except Exception as e:
            raise ValueError(
                f'Failed to cast item ID from {filepath} "{item_id}" as an int: {e}'
            ) from e

    def is_locally_downloaded(self, item: BandcampItem, local_path: Path) -> bool:
        if item.item_id in self.media:
            return True
        id_file = local_path / self.ITEM_INDEX_FILENAME
        if id_file.is_file():
            self.item_names.add((local_path.parent.name, local_path.name))
            try:
                item_id = self.read_item_id(id_file)
            except ValueError as e:
                log.warning(f"Skipping invalid item index file {id_file}: {e}")
            else:
                self.media[item_id] = local_path
                if item_id == item.item_id:
                    log.info(f"Detected locally downloaded media: {item_id} = {local_path}")
                    return True
        item_name = (local_path.parent.name, local_path.name)
        if item_name in self.item_names:
            log.info(
                f'Detected album at "{local_path}" but with an item ID mismatch '
                f"({self.ITEM_INDEX_FILENAME} file does not contain {item.item_id}), "
                f"you may want to check this item is correctly downloaded"
            )
            return True
        return False

    def get_path_for_purchase(self, item: BandcampItem) -> Path:
        # band_name is guaranteed non-None here: Bandcamp.load_purchases() already
        # filters out items with no band_name before they reach self.purchases.
        return (
            self.media_dir
            / self._clean_path(cast(str, item.band_name))
            / self._clean_path(f"{item.item_title}{item.folder_suffix}")
        )

    def get_path_for_file(self, local_path: Path, file_name: str) -> Path:
        return local_path / self._clean_path(file_name)

    def write_bandcamp_id(self, item: BandcampItem, dirpath: Path) -> bool:
        try:
            # A genuinely None item_id still raises here (int(None) is a TypeError),
            # caught below same as any other bad value - the cast doesn't change that.
            item_id = int(cast(int, item.item_id))
        except Exception as e:
            raise ValueError(
                f'Failed to cast item ID for "{dirpath}" "{item.item_id}" as an int: {e}'
            ) from e

        outfile = dirpath / self.ITEM_INDEX_FILENAME
        log.info(f"Writing bandcamp item id:{item_id} to: {outfile}")

        tmp_outfile: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wt",
                delete=False,
                dir=dirpath,
                encoding="utf-8",
            ) as f:
                tmp_outfile = Path(f.name)
                f.write(f"{item_id}\n")
            tmp_outfile.replace(outfile)
        except Exception:
            if tmp_outfile and tmp_outfile.exists():
                tmp_outfile.unlink()
            raise
        return True
