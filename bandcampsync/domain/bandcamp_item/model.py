"""The shape of one Bandcamp collection item: pure data, validated once at
construction, no business methods on it - see checks.py/index.py for what
this data means.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BandcampItem(BaseModel):
    # Not frozen: download_url and folder_suffix are set after construction,
    # once the item's download URL is resolved / a duplicate is detected.
    # validate_assignment re-validates those assignments too.
    model_config = ConfigDict(validate_assignment=True)

    # Required: we're downloading purchases, and a record without an
    # identity isn't a purchase - build_items_from_page() rejects raw
    # collection entries missing any of these outright (letting pydantic
    # do the work) rather than constructing a half-formed item and checking
    # for null fields at every call site downstream.
    item_id: int
    band_name: str = Field(min_length=1)
    item_title: str = Field(min_length=1)
    item_type: str | None = None
    # Real captured payloads send "hidden": null, not false - bool = False
    # would reject that outright. None is already treated as falsy wherever
    # this is read (skip_rules.py's `if ctx.skip_hidden and purchase.hidden`).
    hidden: bool | None = None
    token: str | None = None
    download_url: str | None = None
    folder_suffix: str = ""
    sale_item_type: str | None = None
    sale_item_id: int | None = None
    is_preorder: bool = False
    url_hints: dict[str, Any] | None = None
    purchased: str | None = None
    # extra fields are ignored (pydantic's default): upstream JSON has dozens
    # of fields (currency, price, genre_id, ...) nothing here reads - keep
    # them out of the typed surface instead of smuggling them through.
