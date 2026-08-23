"""Retrieval/shaping: walking a local media directory into a MediaIndex
snapshot, and the pure path computation used to locate a purchase's files.

Uses the shared "media" logger via plain logging.getLogger rather than the
get_logger() wrapper - that wrapper attaches a new StreamHandler every time
it's called, and it's already called once (in domain/media.py) to configure
this same named logger. Calling it again here would double every log line.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from unicodedata import normalize

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.local_media_entry.model import MediaIndex

ITEM_INDEX_FILENAME = "bandcamp_item_id.txt"

log = logging.getLogger("media")


def read_item_id(filepath: Path) -> int:
    with filepath.open() as f:
        item_id = f.read().strip()
    try:
        return int(item_id)
    except Exception as e:
        raise ValueError(
            f'Failed to cast item ID from {filepath} "{item_id}" as an int: {e}'
        ) from e


def index_local_media(
    media_dir: Path,
    on_item_discovered: Callable[[int, str, str], None] | None = None,
) -> MediaIndex:
    """Walks media_dir once for every locally-downloaded item.

    on_item_discovered(item_id, band_name, item_title), if given, is called
    for each one found - this is how a caller (e.g. the service layer) can
    compose in "sync newly-discovered items into the ignore file" without
    this function needing to know ignore_entry exists.
    """
    by_item_id: dict[int, Path] = {}
    item_names: set[tuple[str, str]] = set()
    for child1 in media_dir.iterdir():
        if child1.is_dir():
            for child2 in child1.iterdir():
                if child2.is_dir():
                    for child3 in child2.iterdir():
                        if child3.name == ITEM_INDEX_FILENAME:
                            item_names.add((child2.parent.name, child2.name))
                            try:
                                item_id = read_item_id(child3)
                            except ValueError as e:
                                log.warning(f"Skipping invalid item index file {child3}: {e}")
                                continue
                            by_item_id[item_id] = child2
                            log.info(f"Detected locally downloaded media: {item_id} = {child2}")
                            if on_item_discovered:
                                on_item_discovered(item_id, child2.parent.name, child2.name)
    return MediaIndex(by_item_id=by_item_id, item_names=frozenset(item_names))


def clean_path(path_str: str) -> str:
    path_str = str(path_str)
    disallowed_punctuation = "\"#%'*/?\\`:"
    normalized_path = normalize("NFKD", path_str)
    outstr = ""
    for c in normalized_path:
        if c not in disallowed_punctuation:
            outstr += c
    return outstr


def clean_format(format_str: str) -> str:
    if "-" not in format_str:
        return format_str
    format_parts = format_str.split("-")
    format_prefix = format_parts[0]
    return format_prefix if format_prefix else format_str


def path_for_purchase(media_dir: Path, item: BandcampItem) -> Path:
    return (
        media_dir
        / clean_path(item.band_name)
        / clean_path(f"{item.item_title}{item.folder_suffix}")
    )


def path_for_file(local_path: Path, file_name: str) -> Path:
    return local_path / clean_path(file_name)
