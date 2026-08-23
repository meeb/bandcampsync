"""Pure predicate: should this item be skipped per the configured rules."""

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.ignore_entry.model import IgnoreRules
from bandcampsync.domain.logging_setup import get_logger

log = get_logger("ignores")


def is_ignored(rules: IgnoreRules, item: BandcampItem) -> bool:
    if item.item_id in rules.ids:
        log.warning(
            f"Skipping item {item.band_name} / {item.item_title} due to its id "
            f"{item.item_id} being present in the ignore file"
        )
        return True

    for pattern in rules.band_patterns:
        if pattern in item.band_name.lower():
            log.warning(
                f'Skipping item due to ignore pattern: "{pattern}" found in "{item.band_name}"'
            )
            return True
    return False
