from urllib.parse import urlunsplit

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.interface.bandcamp.constants import BASE_DOMAIN, BASE_PROTO, URLS


def construct_url(url_name: str) -> str:
    if url_name not in URLS:
        raise BandcampError(f"URL name is unknown: {url_name}")
    return urlunsplit((BASE_PROTO, BASE_DOMAIN, URLS[url_name], "", ""))
