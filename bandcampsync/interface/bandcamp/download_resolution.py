import logging

from bandcampsync.domain.bandcamp import BandcampItem

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
        if item.is_physical_purchase():
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
