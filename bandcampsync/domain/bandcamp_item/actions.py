"""Side effects on/about a raw or constructed BandcampItem - nothing here
retrieves or shapes data (that's index.py) or answers a pure question
(that's checks.py).
"""

import logging
from typing import Any

from pydantic import ValidationError

log = logging.getLogger("bandcamp")


def log_invalid_item(raw_item: dict[str, Any], error: ValidationError) -> None:
    """Reports which required field was missing, in the same priority order
    the old per-field if-checks used, so the messages read exactly as before.
    """
    missing = {err["loc"][0] for err in error.errors() if err["loc"]}
    band_name = raw_item.get("band_name")
    item_title = raw_item.get("item_title")
    if "band_name" in missing:
        log.error("Failed to locate band name in item metadata, skipping item...")
    elif "item_title" in missing:
        log.error(
            f"Failed to locate title in item metadata (possibly a subscription?) "
            f'for "{band_name}", skipping item...'
        )
    elif "item_id" in missing:
        log.error(f'Failed to locate item id for "{band_name} / {item_title}", skipping item...')
    else:
        log.error(f"Invalid item metadata, skipping item: {error}")
