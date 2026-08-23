"""Tests for bandcampsync.interface.bandcamp.mixins.download.DownloadMixin.get_download_file_url."""

from unittest.mock import Mock, patch

import pytest

from bandcampsync.domain.bandcamp import BandcampDownloadUnavailable, BandcampError, BandcampItem
from bandcampsync.interface.bandcamp import Bandcamp

_PATCH_TARGET = "bandcampsync.interface.bandcamp.mixins.download.extract_pagedata_from_soup"


@pytest.fixture
def bandcamp() -> Bandcamp:
    instance = Bandcamp("identity=test")
    instance.request = Mock()
    return instance


def _item(item_id=123, download_url="https://bandcamp.com/download/test"):
    return BandcampItem(
        {
            "band_name": "Band",
            "item_title": "Item",
            "item_id": item_id,
            "download_url": download_url,
        }
    )


def test_raises_when_pagedata_is_empty(bandcamp):
    with patch(_PATCH_TARGET, return_value={}), pytest.raises(BandcampError, match="No download"):
        bandcamp.get_download_file_url(_item())


def test_raises_when_digital_items_key_missing(bandcamp):
    with (
        patch(_PATCH_TARGET, return_value={"something_else": []}),
        pytest.raises(BandcampError, match="digital_items"),
    ):
        bandcamp.get_download_file_url(_item())


def test_raises_when_digital_item_missing_item_id(bandcamp):
    pagedata = {"digital_items": [{"no_item_id": True}]}
    with patch(_PATCH_TARGET, return_value=pagedata), pytest.raises(BandcampError, match="art_id"):
        bandcamp.get_download_file_url(_item(item_id=123))


def test_raises_download_unavailable_when_no_matching_item_id(bandcamp):
    pagedata = {"digital_items": [{"item_id": 999}]}
    with (
        patch(_PATCH_TARGET, return_value=pagedata),
        pytest.raises(BandcampDownloadUnavailable, match="No download available for item"),
    ):
        bandcamp.get_download_file_url(_item(item_id=123))


def test_raises_download_unavailable_when_downloads_key_missing(bandcamp):
    pagedata = {"digital_items": [{"item_id": 123}]}
    with (
        patch(_PATCH_TARGET, return_value=pagedata),
        pytest.raises(BandcampDownloadUnavailable, match="No downloads listed"),
    ):
        bandcamp.get_download_file_url(_item(item_id=123))


def test_raises_when_requested_encoding_missing(bandcamp):
    pagedata = {"digital_items": [{"item_id": 123, "downloads": {"mp3-320": {"url": "x"}}}]}
    with (
        patch(_PATCH_TARGET, return_value=pagedata),
        pytest.raises(BandcampError, match="does not contain requested encoding"),
    ):
        bandcamp.get_download_file_url(_item(item_id=123), encoding="flac")


def test_raises_when_url_key_missing_from_encoding(bandcamp):
    pagedata = {"digital_items": [{"item_id": 123, "downloads": {"flac": {"no_url": True}}}]}
    with (
        patch(_PATCH_TARGET, return_value=pagedata),
        pytest.raises(BandcampError, match=r"downloads\.\[encoding\]\.url"),
    ):
        bandcamp.get_download_file_url(_item(item_id=123), encoding="flac")


def test_returns_the_matching_download_url(bandcamp):
    pagedata = {
        "digital_items": [
            {"item_id": 111, "downloads": {"flac": {"url": "https://example.com/wrong"}}},
            {"item_id": 123, "downloads": {"flac": {"url": "https://example.com/right"}}},
        ]
    }
    with patch(_PATCH_TARGET, return_value=pagedata):
        url = bandcamp.get_download_file_url(_item(item_id=123), encoding="flac")

    assert url == "https://example.com/right"
