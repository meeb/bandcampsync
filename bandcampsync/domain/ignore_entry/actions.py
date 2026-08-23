"""Mutation: recording a newly-downloaded item into the ignore file.

Takes the item's identity fields directly rather than a whole BandcampItem -
see checks.py's is_ignored() docstring for why.
"""

from dataclasses import dataclass
from pathlib import Path

from bandcampsync.domain.ignore_entry.model import IgnoreFileLayout
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.domain.utils import atomic_write_text

log = get_logger("ignores")


def record_ignored_item(
    ign_file_path: Path, layout: IgnoreFileLayout, item_id: int, band_name: str, item_title: str
) -> IgnoreFileLayout:
    """Adds item to the ignore file's auto-managed section, returning the
    updated layout for the next call. Logs (rather than raises) on a write
    failure, matching the original Ignores.add()'s tolerance for it - a
    failed write here shouldn't abort an otherwise-successful download.
    """
    # The human-readable comment is ignored by the script but can be useful
    # to identify something that needs a redownload.
    new_lines = [
        *layout.lines[: layout.insert_index],
        f"{item_id}  # {band_name} / {item_title}\n",
        *layout.lines[layout.insert_index :],
    ]
    # The list of ids is in reverse chronological order, like the collection
    # is. The newest items are downloaded in reverse chronological order, so
    # they're added at the top, one after the other, within the session.
    new_layout = IgnoreFileLayout(lines=new_lines, insert_index=layout.insert_index + 1)
    try:
        atomic_write_text(ign_file_path, "".join(new_lines))
    except Exception:
        log.exception(f"Error while adding {item_id} to the ignores.txt file")
    return new_layout


@dataclass
class IgnoreFileWriter:
    """Mutable, session-scoped holder that accumulates the ignore file's
    layout as newly-downloaded items are recorded during one sync run - the
    thin imperative shell around the pure record_ignored_item() above, so
    callers don't have to thread the returned layout through themselves.
    """

    ign_file_path: Path | None
    layout: IgnoreFileLayout

    def record(self, item_id: int, band_name: str, item_title: str) -> None:
        # We assume that if you use an "ignore" file once, you'll keep using
        # it forever (e.g. Docker). If you don't, this is a no-op and
        # callers fall back to the per-directory id file instead.
        if not self.ign_file_path:
            return
        self.layout = record_ignored_item(
            self.ign_file_path, self.layout, item_id, band_name, item_title
        )
