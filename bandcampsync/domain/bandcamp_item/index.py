"""Retrieval/shaping: turn raw collection-page JSON into validated
BandcampItems. No HTTP here and no pagination loop - that's Bandcamp's own
transport mechanic and stays in interface/bandcamp/mixins/fancollection.py.
"""

import logging
from typing import Any

from pydantic import ValidationError

from bandcampsync.domain.bandcamp_item.actions import log_invalid_item
from bandcampsync.domain.bandcamp_item.checks import is_physical_purchase
from bandcampsync.domain.bandcamp_item.model import BandcampItem

log = logging.getLogger("bandcamp")


def resolve_download_url(item: BandcampItem, redownload_urls: dict[str, str]) -> str | None:
    sale_item_type = item.sale_item_type
    sale_item_id = item.sale_item_id
    if sale_item_type is None or sale_item_id is None:
        log.error(
            f"Failed to locate sale item metadata for {item.band_name} / "
            f"{item.item_title}, skipping item..."
        )
        return None
    download_url_key = f"{sale_item_type}{sale_item_id}"
    download_url = redownload_urls.get(download_url_key)
    if not download_url:
        if is_physical_purchase(item):
            log.info(
                f"No download available for physical purchase {item.band_name} / "
                f"{item.item_title} (key:{download_url_key}), skipping"
            )
        else:
            log.warning(
                f"No download available for {item.band_name} / {item.item_title} "
                f"(key:{download_url_key}), skipping item..."
            )
        return None
    return download_url


def build_items_from_page(
    raw_items: list[dict[str, Any]], redownload_urls: dict[str, str]
) -> list[BandcampItem]:
    """Validates one page of raw collection JSON into BandcampItems, skipping
    (and logging) entries missing band_name/item_title/item_id, and resolving
    each surviving item's download_url (left None if unresolvable - it's up
    to the caller whether an item without one still counts as "found").
    """
    items = []
    for raw_item in raw_items:
        try:
            item = BandcampItem(**raw_item)
        except ValidationError as e:
            log_invalid_item(raw_item, e)
            continue
        item.download_url = resolve_download_url(item, redownload_urls)
        items.append(item)
    return items


def deduplicate_purchases(items: list[BandcampItem]) -> None:
    grouped: dict[tuple[str, str], list[BandcampItem]] = {}
    for item in items:
        grouped.setdefault((item.band_name, item.item_title), []).append(item)

    for group in grouped.values():
        count = len(group)
        if count == 1:
            continue
        duplicate = group[0]
        item_ids = ", ".join(str(item.item_id) for item in group)
        log.info(
            f"Found {count} collection entries with the same name: "
            f'"{duplicate.band_name} / {duplicate.item_title}" (ids: {item_ids})'
        )
        duplicate_details = []
        for item in group:
            log.debug(f"Duplicate entry: url={item.download_url}")
            duplicate_details.append(
                f"id={item.item_id} item_type={item.item_type or ''} "
                f"sale_item_type={item.sale_item_type} sale_item_id={item.sale_item_id}"
            )
            # Use the item ID as a suffix to ensure duplicates are downloaded
            # to distinct folders.
            item.folder_suffix = f" [{item.item_id}]"
        log.debug(
            f"Duplicate name details: {duplicate.band_name} / {duplicate.item_title}: "
            f"{', '.join(duplicate_details)}"
        )
