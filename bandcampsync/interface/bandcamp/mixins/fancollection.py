"""POST /api/fancollection/1/collection_items (URLS["collection_items"]) -
paginating through the account's purchased collection.
"""

from collections.abc import Callable
from time import time

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.domain.bandcamp_item import (
    BandcampItem,
    build_items_from_page,
    deduplicate_purchases,
)
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.interface.bandcamp.base import BandcampClientBase
from bandcampsync.interface.bandcamp.urls import construct_url

log = get_logger("bandcamp")


class FanCollectionMixin(BandcampClientBase):
    def load_purchases(self, stop_when: Callable[[BandcampItem], bool] | None = None) -> bool:
        """Loads all purchases on the authenticated account and returns a list of
        purchase data. Each purchase is a dict of data.
        If stop_when is provided, it is called for every parsed BandcampItem and
        should return True to stop pagination early.
        """
        # request()'s own auth guard fires too late for us: fan_id below reads
        # self.user_id before the first request is even built, so it needs
        # authenticating up front rather than lazily on first dispatch.
        if not self.is_authenticated:
            self.verify_authentication()
        log.info(f"Loading purchases for user id: {self.user_id}")
        self.purchases = []
        self.collection_items = []
        now = int(time())
        page_ts = 0
        token = f"{now}:{page_ts}:a::"
        per_page = 100
        stop_loading = False
        while True:
            log.info(f"Requesting {per_page} purchases using token {token}")
            request_data = {
                "fan_id": self.user_id,
                "count": per_page,
                "older_than_token": token,
            }
            url = construct_url("collection_items")
            data = self.request("POST", url, json_data=request_data, is_json=True)
            try:
                raw_items = data["items"]
            except KeyError as e:
                raise BandcampError("Failed to extract items from collection results page") from e
            if not raw_items:
                log.info("Reached end of items")
                break
            try:
                redownload_urls = data["redownload_urls"]
            except KeyError as e:
                raise BandcampError(
                    "Failed to extract redownload_urls from collection results page"
                ) from e

            # The pagination cursor must advance from every raw item, valid
            # or not - it's the raw JSON's own token, not the constructed
            # (and possibly skipped) BandcampItem's.
            for raw_item in raw_items:
                raw_token = raw_item.get("token")
                if raw_token is not None:
                    token = raw_token

            for item in build_items_from_page(raw_items, redownload_urls):
                self.collection_items.append(item)
                if stop_when and stop_when(item):
                    stop_loading = True
                    break
                if item.download_url:
                    log.info(
                        f"Found item: {item.band_name} / {item.item_title} (id:{item.item_id})"
                    )
                    self.purchases.append(item)
            if stop_loading:
                log.info("Stopping purchase pagination early due to stop condition")
                break

        # De-duplicate multiple purchases sharing the same artist and title.
        deduplicate_purchases(self.purchases)
        log.info(f"Loaded {len(self.purchases)} purchases")
        return True
