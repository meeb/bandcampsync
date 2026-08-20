"""POST /api/fancollection/1/collection_items (URLS["collection_items"]) -
paginating through the account's purchased collection.
"""

from collections.abc import Callable
from time import time

from bandcampsync.domain.bandcamp import BandcampError, BandcampItem
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.interface.bandcamp.base import BandcampClientBase
from bandcampsync.interface.bandcamp.deduplication import deduplicate_purchases
from bandcampsync.interface.bandcamp.download_resolution import resolve_download_url
from bandcampsync.interface.bandcamp.urls import construct_url

log = get_logger("bandcamp")


class FanCollectionMixin(BandcampClientBase):
    def load_purchases(self, stop_when: Callable[[BandcampItem], bool] | None = None) -> bool:
        """Loads all purchases on the authenticated account and returns a list of
        purchase data. Each purchase is a dict of data.
        If stop_when is provided, it is called for every parsed BandcampItem and
        should return True to stop pagination early.
        """
        if not self.is_authenticated:
            raise BandcampError("Authentication not verified, call load_pagedata() first")
        log.info(f"Loading purchases for user id: {self.user_id}")
        self.purchases = []
        self.collection_items = []
        now = int(time())
        page_ts = 0
        token = f"{now}:{page_ts}:a::"
        per_page = 100
        items_by_title_key: dict[tuple[str | None, str | None], list[BandcampItem]] = {}
        stop_loading = False
        while True:
            log.info(f"Requesting {per_page} purchases using token {token}")
            request_data = {
                "fan_id": self.user_id,
                "count": per_page,
                "older_than_token": token,
            }
            url = construct_url("collection_items")
            data = self._request("POST", url, json_data=request_data, is_json=True)
            try:
                items = data["items"]
            except KeyError as e:
                raise BandcampError("Failed to extract items from collection results page") from e
            if not items:
                log.info("Reached end of items")
                break
            try:
                redownload_urls = data["redownload_urls"]
            except KeyError as e:
                raise BandcampError(
                    "Failed to extract redownload_urls from collection results page"
                ) from e
            for item_data in items:
                item = BandcampItem(item_data)
                item_token = item.token
                if item_token is not None:
                    token = item_token
                if not item.band_name:
                    log.error("Failed to locate band name in item metadata, skipping item...")
                    continue
                if not item.item_title:
                    log.error(
                        f"Failed to locate title in item metadata (possibly a subscription?) "
                        f'for "{item.band_name}", skipping item...'
                    )
                    continue
                if item.item_id is None:
                    log.error(
                        f'Failed to locate item id for "{item.band_name} / {item.item_title}", '
                        f"skipping item..."
                    )
                    continue
                self.collection_items.append(item)
                if stop_when and stop_when(item):
                    stop_loading = True
                    break
                download_url = resolve_download_url(item, redownload_urls)
                if not download_url:
                    continue
                item.download_url = download_url
                item_key = (item.band_name, item.item_title)
                items_by_title_key.setdefault(item_key, []).append(item)
                log.info(f"Found item: {item.band_name} / {item.item_title} (id:{item.item_id})")
                self.purchases.append(item)
            if stop_loading:
                log.info("Stopping purchase pagination early due to stop condition")
                break

        # De-duplicate multiple purchases sharing the same artist and title.
        deduplicate_purchases(items_by_title_key)
        log.info(f"Loaded {len(self.purchases)} purchases")
        return True
