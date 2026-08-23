"""Tests for bandcampsync.domain.bandcamp_item.index."""

import json
import logging
from pathlib import Path

import pytest

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.bandcamp_item.index import (
    build_items_from_page,
    deduplicate_purchases,
    resolve_download_url,
)
from tests.factories import make_raw_item


def _load_payload(name):
    fixture_path = Path(__file__).resolve().parent / "data" / name
    return json.loads(fixture_path.read_text(encoding="utf-8", errors="ignore"))


def _download_key(item):
    return f"{item['sale_item_type']}{item['sale_item_id']}"


@pytest.fixture
def digital_payload():
    return _load_payload("collection-item-digital-only.json")


@pytest.fixture
def physical_payload():
    return _load_payload("collection-item-physical-only.json")


@pytest.fixture
def digital_item(digital_payload):
    return digital_payload["items"][0]


@pytest.fixture
def physical_item(physical_payload):
    return physical_payload["items"][0]


def test_resolve_download_url_digital(digital_payload, digital_item):
    item = BandcampItem(**digital_item)

    download_url = resolve_download_url(item, digital_payload["redownload_urls"])

    expected_key = _download_key(digital_item)
    assert download_url == digital_payload["redownload_urls"][expected_key]


def test_resolve_download_url_physical(physical_payload, physical_item):
    item = BandcampItem(**physical_item)

    download_url = resolve_download_url(item, physical_payload["redownload_urls"])

    assert download_url is None


def _item(item_id, **overrides):
    return BandcampItem(
        **make_raw_item(
            item_id=item_id,
            sale_item_id=item_id,
            download_url="https://example.com/download",
            **overrides,
        )
    )


def test_dedup_leaves_unique_items_untouched():
    item = _item(1)
    deduplicate_purchases([item])

    assert item.folder_suffix == ""


def test_dedup_adds_item_id_suffix_to_every_duplicate():
    items = [_item(1), _item(2), _item(3)]
    deduplicate_purchases(items)

    assert [item.folder_suffix for item in items] == [" [1]", " [2]", " [3]"]


def test_dedup_only_groups_items_sharing_band_and_title():
    unique = _item(1, item_title="Solo Album")
    duplicates = [_item(2), _item(3)]
    deduplicate_purchases([unique, *duplicates])

    assert unique.folder_suffix == ""
    assert [item.folder_suffix for item in duplicates] == [" [2]", " [3]"]


def test_build_items_from_page_skips_entries_missing_required_fields(caplog):
    caplog.set_level(logging.ERROR, logger="bandcamp")
    raw_items = [
        {"item_id": 1, "item_title": "Album"},  # missing band_name
        {"item_id": 2, "band_name": "Band"},  # missing item_title
        {"band_name": "Band", "item_title": "Album"},  # missing item_id
        make_raw_item(item_id=3, band_name="Band", item_title="Album"),
    ]

    items = build_items_from_page(raw_items, redownload_urls={})

    assert [item.item_id for item in items] == [3]


def test_build_items_from_page_resolves_download_url():
    raw_items = [make_raw_item(item_id=1, sale_item_type="a", sale_item_id=1)]

    items = build_items_from_page(raw_items, redownload_urls={"a1": "https://example.com/dl"})

    assert items[0].download_url == "https://example.com/dl"
