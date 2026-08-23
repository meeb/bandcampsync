"""Mutation: writing the bandcamp_item_id.txt marker file for a purchase.

Uses the shared "media" logger via plain logging.getLogger, not get_logger()
- see index.py's docstring for why (domain/media.py already attaches the
handler once).
"""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.local_media_entry.index import ITEM_INDEX_FILENAME

log = logging.getLogger("media")


def write_bandcamp_id(item: BandcampItem, dirpath: Path) -> bool:
    try:
        item_id = int(item.item_id)
    except Exception as e:
        raise ValueError(
            f'Failed to cast item ID for "{dirpath}" "{item.item_id}" as an int: {e}'
        ) from e

    outfile = dirpath / ITEM_INDEX_FILENAME
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
