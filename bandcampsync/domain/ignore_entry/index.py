"""Retrieval: parses the on-disk ignore file (and the CLI ignore patterns)
into IgnoreRules, plus the IgnoreFileLayout needed to rewrite the file later.
"""

import re
import shutil
from pathlib import Path

from bandcampsync.domain.ignore_entry.model import IgnoreFileLayout, IgnoreRules
from bandcampsync.domain.logging_setup import get_logger

TEMPLATE_IGNORES_FILE = "/ignores.template.txt"
# A comment containing 10 or more equals signs,
# used to delimit user-entered data with ids from the last run
DELIMITER_REGEX = re.compile(r"^#\s*={10,}\s*$")
log = get_logger("ignores")


def load_ignore_rules(
    ign_file_path: Path | None, ign_patterns: str
) -> tuple[IgnoreRules, IgnoreFileLayout]:
    band_patterns = tuple(pattern.lower() for pattern in ign_patterns.split())
    if band_patterns:
        log.info(f"Using {len(band_patterns)} ignore patterns")

    if not ign_file_path:
        log.info("No ignore file specified")
        return IgnoreRules(band_patterns=band_patterns), IgnoreFileLayout()

    log.info(f"Ignore file: {ign_file_path}")

    # If a file path is specified, but there is no such file (e.g. first
    # run on Docker), we create it. We can't do it in the Dockerfile
    # because it must be created in the mounted volume.
    if not ign_file_path.exists():
        log.warning(f"Ignore file {ign_file_path} not found. Creating a blank one")
        shutil.copyfile(TEMPLATE_IGNORES_FILE, ign_file_path)

    with ign_file_path.open() as f:
        try:
            ign_lines = f.readlines()
        except Exception as e:
            raise ValueError(f"Failed to read ignore file {ign_file_path}: {e}") from e

    # Find the location of the separator
    insert_index = -1
    for i, line in enumerate(ign_lines):
        if DELIMITER_REGEX.match(line):
            insert_index = i + 1
            break

    # If it's missing, add one at the end.
    # Note that the blank "ignores" file does not contain this section, so that
    # this code is the only source of truth for what it looks like.
    if insert_index == -1:
        ign_lines.append("\n")
        ign_lines.append(
            "# IDs of items already downloaded will be automatically added below this line.\n"
        )
        ign_lines.append("# =========================================================\n")
        insert_index = len(ign_lines)

    # We keep the original lines as the base to add content to later, but
    # process the parsed content into the "lines" variable here.
    lines = [line.split("#")[0].strip() for line in ign_lines]  # Strip comments
    lines = [line for line in lines if line]  # Remove empty lines
    ids = set()
    for line in lines:
        try:
            ids.add(int(line))
        # small, startup-time-only file; try/except cost is a non-issue
        except Exception as e:  # noqa: PERF203
            raise ValueError(
                f'Failed to cast item ID from {ign_file_path} "{line}" as an int: {e}'
            ) from e

    rules = IgnoreRules(ids=frozenset(ids), band_patterns=band_patterns)
    layout = IgnoreFileLayout(lines=ign_lines, insert_index=insert_index)
    return rules, layout
