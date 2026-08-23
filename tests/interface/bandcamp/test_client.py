"""Tests for bandcampsync.interface.bandcamp.client.Bandcamp."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from bandcampsync.domain.bandcamp import BandcampDownloadUnavailable
from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.interface.bandcamp import Bandcamp


def _load_payload(name):
    fixture_path = Path(__file__).resolve().parent / "data" / name
    return json.loads(fixture_path.read_text(encoding="utf-8", errors="ignore"))


def _create_bandcamp():
    bandcamp = Bandcamp("identity=test")
    bandcamp.is_authenticated = True
    bandcamp.user_id = 1
    return bandcamp


@pytest.fixture
def bandcamp():
    return _create_bandcamp()


@pytest.fixture
def physical_payload():
    return _load_payload("collection-item-physical-only.json")


@pytest.fixture
def physical_item(physical_payload):
    return physical_payload["items"][0]


def test_load_purchases_can_stop_at_physical_only_item(bandcamp, physical_payload, physical_item):
    bandcamp.request = Mock(return_value=physical_payload)

    bandcamp.load_purchases(
        stop_when=lambda item: (
            item.band_name == physical_item["band_name"]
            and item.item_title == physical_item["item_title"]
        )
    )

    assert [item.item_id for item in bandcamp.collection_items] == [physical_item["item_id"]]
    assert bandcamp.purchases == []


def test_get_download_file_url_missing_downloads_is_unavailable(bandcamp):
    item = BandcampItem(
        band_name="Scuba",
        item_title="Hardcore Heaven II",
        item_id=123,
        download_url="https://bandcamp.com/download/test",
        item_type="album",
        token="t",
        sale_item_type="a",
        sale_item_id=123,
        purchased="01 Jan 2026 00:00:00 GMT",
    )
    bandcamp.request = Mock()

    with (
        patch(
            "bandcampsync.interface.bandcamp.mixins.download.extract_pagedata_from_soup",
            return_value={"digital_items": [{"item_id": 123}]},
        ),
        pytest.raises(BandcampDownloadUnavailable),
    ):
        bandcamp.get_download_file_url(item)
