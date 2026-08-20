"""GET /download/... and /statdownload/... - resolving and verifying a
purchased item's actual download URL.
"""

from typing import cast
from urllib.parse import urlsplit, urlunsplit

from bandcampsync.domain.bandcamp import BandcampDownloadUnavailable, BandcampError, BandcampItem
from bandcampsync.interface.bandcamp.base import BandcampClientBase
from bandcampsync.interface.bandcamp.pagedata import extract_pagedata_from_soup
from bandcampsync.interface.bandcamp.stat_url import parse_js_stat_url


class DownloadMixin(BandcampClientBase):
    def get_download_file_url(self, item: BandcampItem, encoding: str = "flac") -> str:
        # download_url is always set by this point: load_purchases() only appends an
        # item to self.purchases after resolving and assigning its download_url.
        soup = self._request("get", cast(str, item.download_url))
        pagedata = extract_pagedata_from_soup(soup, id_name="pagedata")
        if not pagedata:
            raise BandcampError("No download information found for item")
        try:
            digital_items = pagedata["digital_items"]
        except KeyError as e:
            raise BandcampError(
                'Failed to parse pagedata JSON, does not contain an "digital_items" key'
            ) from e
        for digital_item in digital_items:
            try:
                digital_item_id = digital_item["item_id"]
            except KeyError as e:
                raise BandcampError(
                    "Failed to parse pagedata JSON, does not contain an "
                    '"digital_items[].art_id" key'
                ) from e
            if digital_item_id == item.item_id:
                try:
                    downloads = digital_item["downloads"]
                except KeyError as e:
                    raise BandcampDownloadUnavailable(
                        f"No downloads listed for {item.band_name} / {item.item_title}"
                    ) from e
                try:
                    download_format = downloads[encoding]
                except KeyError as e:
                    encodings = downloads.keys()
                    raise BandcampError(
                        f"Download formats does not contain requested encoding: {encoding} "
                        f"(available encodings: {encodings})"
                    ) from e
                try:
                    return cast(str, download_format["url"])
                except KeyError as e:
                    raise BandcampError(
                        "Failed to parse pagedata JSON, does not contain an "
                        '"digital_items.downloads.[encoding].url" key'
                    ) from e
        raise BandcampDownloadUnavailable("No download available for item")

    def check_download_stat(self, item: BandcampItem, file_download_url: str) -> str:
        """Constructs the download "stat" URL and verifies the state of the download.
        If the state is OK, return the existing URL (download is OK), otherwise wait
        for the stat to complete and return the new download URL.
        """
        download_url_parts = urlsplit(file_download_url)
        path = download_url_parts.path
        path_parts = path.split("/")
        if path_parts[1] == "download":
            path_parts[1] = "statdownload"
        stat_url = urlunsplit(
            (
                download_url_parts.scheme,
                download_url_parts.netloc,
                "/".join(path_parts),
                download_url_parts.query,
                "",
            )
        )
        body = self._request("get", stat_url, as_raw=True)
        return parse_js_stat_url(body, file_download_url)
