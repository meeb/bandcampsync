"""Shared test factories.

make_bandcamp_item() builds a BandcampItem from a real captured collection
API response (tests/domain/bandcamp_item/data/collection-item-digital-only.json),
overridden per-test - rather than every test file hand-listing the handful
of fields BandcampItem happens to require right now. Passing a whole real
response object and letting pydantic pick out what it needs is also just a
more honest fixture: it's what the API actually sends, not a guessed-at
minimal shape.
"""

import json
from pathlib import Path
from typing import Any

from bandcampsync.domain.bandcamp_item import BandcampItem

_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "domain"
    / "bandcamp_item"
    / "data"
    / "collection-item-digital-only.json"
)
_BASE_ITEM: dict[str, Any] = json.loads(_FIXTURE_PATH.read_text())["items"][0]


def make_bandcamp_item(**overrides: Any) -> BandcampItem:
    return BandcampItem(**{**_BASE_ITEM, **overrides})


def make_raw_item(**overrides: Any) -> dict[str, Any]:
    """The dict form, for tests feeding raw (unvalidated) API JSON through
    build_items_from_page() rather than constructing BandcampItem directly.
    """
    return {**_BASE_ITEM, **overrides}
