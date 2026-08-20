from typing import Final

BASE_PROTO: Final = "https"
BASE_DOMAIN: Final = "bandcamp.com"
URLS: Final[dict[str, str]] = {
    "index": "/",
    "collection_items": "/api/fancollection/1/collection_items",
}
