"""Warns when items are only tracked via the legacy per-directory id file
instead of the shared ignore file, and how to migrate them.
"""

import logging
from pathlib import Path

logger = logging.getLogger("sync")

# NOTE: "orrun" (missing space) below is a preserved upstream typo, not a new one.
_MESSAGE = """\
The {ign_file_path} file is tracking already downloaded items, but some \
directories are using bandcamp_item_id.txt files. If you want to get migrate \
from ID files to using the {ign_file_path} file, pass the '--sync-ignore-file' \
flag, or\
run the following script inside the downloads directory, then append \
the content of the new ignores.txt file to the ignores file in your config \
directory:
  find . -name "bandcamp_item_id.txt" \\
    | while read -r id_file
      do \\
        comment="$(echo "$id_file" \\
            | sed -r -e "s%./([^/]+)/([^/]+)/bandcamp_item_id.txt%\\1 / \\2%")"
        echo "$(cat "$id_file")  # $comment"
        rm "$id_file"
      done >> ignores.txt
"""


def log_id_file_migration_warning_if_needed(
    show_id_file_warning: bool, sync_ignore_file: bool, ign_file_path: Path | None
) -> None:
    # We don't need to show this warning if we're running the ignorefile sync script
    if not show_id_file_warning or sync_ignore_file:
        return
    logger.warning(_MESSAGE.format(ign_file_path=ign_file_path))
