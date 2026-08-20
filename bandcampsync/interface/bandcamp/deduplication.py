import logging
from typing import Any

from bandcampsync.domain.bandcamp import BandcampItem

log = logging.getLogger("bandcamp")


def deduplicate_purchases(grouped_items: dict[Any, list[BandcampItem]]) -> None:
    for items in grouped_items.values():
        count = len(items)
        if count == 1:
            continue
        duplicate = items[0]
        item_ids = ", ".join(str(item.item_id) for item in items)
        log.info(
            f"Found {count} collection entries with the same name: "
            f'"{duplicate.band_name} / {duplicate.item_title}" (ids: {item_ids})'
        )
        duplicate_details = []
        for item in items:
            log.debug(f"Duplicate entry: url={item.download_url}")
            duplicate_details.append(
                f"id={item.item_id} item_type={getattr(item, 'item_type', '')} "
                f"sale_item_type={item.sale_item_type} sale_item_id={item.sale_item_id}"
            )
            # Use the item ID as a suffix to ensure duplicates are downloaded
            # to distinct folders.
            item.folder_suffix = f" [{item.item_id}]"
        log.debug(
            f"Duplicate name details: {duplicate.band_name} / {duplicate.item_title}: "
            f"{', '.join(duplicate_details)}"
        )
