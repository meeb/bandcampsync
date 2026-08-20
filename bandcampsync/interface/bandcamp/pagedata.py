import json
from html import unescape as html_unescape
from typing import Any, cast

from bs4 import BeautifulSoup

from bandcampsync.domain.bandcamp import BandcampError


def extract_pagedata_from_soup(soup: Any, id_name: str = "pagedata") -> dict[str, Any]:
    pagedata_tag = soup.find("div", id=id_name)
    if not pagedata_tag:
        raise BandcampError(
            f'Failed to locate <div id="{id_name}"> in HTML, this may '
            "be an authentication issue or it may be that bandcamp.com has "
            "updated their website and this tool needs to be updated."
        )
    encoded_pagedata = pagedata_tag.attrs.get("data-blob")
    if not encoded_pagedata:
        raise BandcampError(
            "Failed to extract page data, check your cookies are from an ",
            "authenticated session",
        )
    pagedata_str = html_unescape(encoded_pagedata)
    try:
        return cast(dict[str, Any], json.loads(pagedata_str))
    except Exception as e:
        raise BandcampError(f"Failed to parse pagedata as JSON: {e}") from e


def extract_pagedata_from_html(html: str) -> dict[str, Any]:
    """Wrapper for extract_pagedata_from_soup() that can accept HTML rather than a bs4 soup."""
    soup = BeautifulSoup(html, "html.parser")
    return extract_pagedata_from_soup(soup)
