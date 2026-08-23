"""Pure predicate: should this item be skipped per the configured rules.

Takes the item's identity fields directly rather than a whole BandcampItem -
this is also used for items reconciled purely from a local directory (see
domain/media.py), which were never fetched from the API and can't supply a
full purchase record (item_type, token, sale metadata, ...).
"""

from bandcampsync.domain.ignore_entry.model import IgnoreRules
from bandcampsync.domain.logging_setup import get_logger

log = get_logger("ignores")


def is_ignored(rules: IgnoreRules, item_id: int, band_name: str, item_title: str) -> bool:
    if item_id in rules.ids:
        log.warning(
            f"Skipping item {band_name} / {item_title} due to its id "
            f"{item_id} being present in the ignore file"
        )
        return True

    for pattern in rules.band_patterns:
        if pattern in band_name.lower():
            log.warning(f'Skipping item due to ignore pattern: "{pattern}" found in "{band_name}"')
            return True
    return False
