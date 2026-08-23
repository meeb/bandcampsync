"""Query: is this item already downloaded locally.

Takes plain mutable dict/set rather than a MediaIndex: this check can
lazily discover a per-directory id file the eager walk didn't have (e.g.
when index_on_init=False), and needs to record that discovery somewhere
callers can see on the next call. A plain caller-owned dict/set makes that
mutation explicit at the call site, rather than hiding it inside an object
method the way the old LocalMedia class did.

Uses the shared "media" logger via plain logging.getLogger, not get_logger()
- see index.py's docstring for why (domain/media.py already attaches the
handler once).
"""

import logging
from pathlib import Path

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.local_media_entry.index import ITEM_INDEX_FILENAME, read_item_id

log = logging.getLogger("media")


def is_locally_downloaded(
    media: dict[int, Path],
    item_names: set[tuple[str, str]],
    item: BandcampItem,
    local_path: Path,
) -> bool:
    if item.item_id in media:
        return True
    id_file = local_path / ITEM_INDEX_FILENAME
    if id_file.is_file():
        item_names.add((local_path.parent.name, local_path.name))
        try:
            item_id = read_item_id(id_file)
        except ValueError as e:
            log.warning(f"Skipping invalid item index file {id_file}: {e}")
        else:
            media[item_id] = local_path
            if item_id == item.item_id:
                log.info(f"Detected locally downloaded media: {item_id} = {local_path}")
                return True
    item_name = (local_path.parent.name, local_path.name)
    if item_name in item_names:
        log.info(
            f'Detected album at "{local_path}" but with an item ID mismatch '
            f"({ITEM_INDEX_FILENAME} file does not contain {item.item_id}), "
            f"you may want to check this item is correctly downloaded"
        )
        return True
    return False
