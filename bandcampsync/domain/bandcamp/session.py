"""The narrow slice of Bandcamp session behaviour domain/sync/item.py actually
needs, as a structural Protocol. interface.bandcamp.Bandcamp satisfies this
without depending on (or even knowing about) it - the dependency points
inward: domain declares what it needs, interface provides it.
"""

from typing import IO, Any, Protocol

from bandcampsync.domain.bandcamp_item import BandcampItem


class BandcampSession(Protocol):
    """Bandcamp session operations needed to resolve and fetch a single
    purchased item's download.

    Raises
    ------
    BandcampError
        If Bandcamp's response cannot be parsed as expected.
    BandcampDownloadUnavailable
        If Bandcamp reports no download is available for the item.
    BandcampDownloadExpired
        If the download link has expired and needs reconfirming on Bandcamp.
    """

    def get_download_file_url(self, item: BandcampItem, encoding: str = ...) -> str: ...
    def check_download_stat(self, item: BandcampItem, file_download_url: str) -> str: ...
    def fetch_purchase_file(self, url: str, target: IO[Any]) -> str: ...
