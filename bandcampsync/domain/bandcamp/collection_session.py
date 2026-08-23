"""The narrow slice of Bandcamp session behaviour service/sync_collection.py
actually needs to authenticate and paginate the collection, as a structural
Protocol. interface.bandcamp.Bandcamp satisfies this without depending on
(or even knowing about) it - the dependency points inward: domain declares
what it needs, interface provides it.

Deliberately separate from BandcampSession (session.py): that protocol
covers per-item downloading for download_purchase's context, which has no
use for verify_authentication/load_purchases/purchases/collection_items,
and this one has no use for get_download_file_url/check_download_stat/
fetch_purchase_file (interface segregation). A single Bandcamp instance
satisfies both structurally.
"""

from collections.abc import Callable
from typing import Protocol

from bandcampsync.domain.bandcamp.item import BandcampItem


class BandcampCollectionSession(Protocol):
    purchases: list[BandcampItem]
    collection_items: list[BandcampItem]

    def verify_authentication(self) -> bool: ...
    def load_purchases(self, stop_when: Callable[[BandcampItem], bool] | None = None) -> bool: ...
