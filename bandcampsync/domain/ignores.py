import re
import shutil
from pathlib import Path
from typing import cast

from bandcampsync.domain.bandcamp import BandcampItem
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.domain.utils import atomic_write_text

TEMPLATE_IGNORES_FILE = "/ignores.template.txt"
# A comment containing 10 or more equals signs,
# used to delimit user-entered data with ids from the last run
DELIMITER_REGEX = re.compile(r"^#\s*={10,}\s*$")
log = get_logger("ignores")


class Ignores:
    """Manages configuration for items that shouldn't be downloaded."""

    def __init__(self, ign_file_path: Path | None, ign_patterns: str) -> None:
        self.ign_file_path = ign_file_path
        if self.ign_file_path:
            log.info(f"Ignore file: {self.ign_file_path}")
        # List of substring patterns for band_name
        self.band_patterns = [pattern.lower() for pattern in ign_patterns.split()]
        if self.band_patterns:
            log.info(f"Using {len(self.band_patterns)} ignore patterns")

        # The original lines of the "ignores" file. Used to rewrite it whenever it's changed.
        self.ign_lines: list[str] = []
        # The line number at which to insert the next downloaded item id
        self.ign_insert_index = -1
        self.ids: set[int] = set()
        self.parse_ignores()

    def parse_ignores(self) -> None:
        if not self.ign_file_path:
            log.info("No ignore file specified")
            return

        # If a file path is specified, but there is no such file (e.g. first
        # run on Docker), we create it. We can't do it in the Dockerfile
        # because it must be created in the mounted volume.
        if not self.ign_file_path.exists():
            log.warning(f"Ignore file {self.ign_file_path} not found. Creating a blank one")
            shutil.copyfile(TEMPLATE_IGNORES_FILE, self.ign_file_path)

        with self.ign_file_path.open() as f:
            try:
                self.ign_lines = f.readlines()
            except Exception as e:
                raise ValueError(f"Failed to read ignore file {self.ign_file_path}: {e}") from e

        # Find the location of the separator
        for i, line in enumerate(self.ign_lines):
            if DELIMITER_REGEX.match(line):
                self.ign_insert_index = i + 1
                break

        # If it's missing, add one at the end.
        # Note that the blank "ignores" file does not contain this section, so that
        # this code is the only source of truth for what it looks like.
        if self.ign_insert_index == -1:
            self.ign_lines.append("\n")
            self.ign_lines.append(
                "# IDs of items already downloaded will be automatically added below this line.\n"
            )
            self.ign_lines.append("# =========================================================\n")
            self.ign_insert_index = len(self.ign_lines)

        # We keep the original lines in self.ign_lines as base to add content,
        # but we process the parsed content into the "lines" variable.
        lines = [line.split("#")[0].strip() for line in self.ign_lines]  # Strip comments
        lines = [line for line in lines if line]  # Remove empty lines
        for line in lines:
            try:
                self.ids.add(int(line))
            # small, startup-time-only file; try/except cost is a non-issue
            except Exception as e:  # noqa: PERF203
                raise ValueError(
                    f'Failed to cast item ID from {self.ign_file_path} "{line}" as an int: {e}'
                ) from e

    def add(self, item: BandcampItem) -> None:
        """Adds a new item to the "ignores" file in the auto-managed section."""
        if not self.ign_file_path:
            return

        # We recreate the content of the file from the initial read.
        # Note that any manual change made to the "ignores" file while the process is running
        # will be lost because we only read the content at startup time.
        self.ign_lines = [
            *self.ign_lines[: self.ign_insert_index],
            # The human-readable comment is ignored by the script
            # but can be useful to identify something that needs a redownload
            f"{item.item_id}  # {item.band_name} / {item.item_title}\n",
            *self.ign_lines[self.ign_insert_index :],
        ]
        # The list of ids is in reverse chronological order, like the collection is.
        # The newest items are downloaded in reverse chronological order, so we add
        # them at the top, one after the other, within the session.
        self.ign_insert_index += 1

        try:
            atomic_write_text(self.ign_file_path, "".join(self.ign_lines))
        except Exception:
            log.exception(f"Error while adding {item.item_id} to the ignores.txt file")

    def is_ignored(self, item: BandcampItem) -> bool:
        # Check if the id is ignored
        if item.item_id in self.ids:
            log.warning(
                f"Skipping item {item.band_name} / {item.item_title} due to its id "
                f"{item.item_id} being present in the ignore file"
            )
            return True

        # Check if any "ignore" pattern matches the band name. band_name is
        # guaranteed non-None here: Bandcamp.load_purchases() already filters out
        # items with no band_name before they can reach self.purchases.
        for pattern in self.band_patterns:
            if pattern in cast(str, item.band_name).lower():
                log.warning(
                    f'Skipping item due to ignore pattern: "{pattern}" found in "{item.band_name}"'
                )
                return True
        return False
