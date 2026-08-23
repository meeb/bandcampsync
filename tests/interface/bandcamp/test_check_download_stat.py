"""Tests for bandcampsync.interface.bandcamp.mixins.download.DownloadMixin.check_download_stat."""

from unittest.mock import Mock

import pytest

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.interface.bandcamp import Bandcamp


@pytest.fixture
def bandcamp() -> Bandcamp:
    instance = Bandcamp("identity=test")
    instance.request = Mock()
    return instance


def _item():
    return BandcampItem(band_name="Band", item_title="Item", item_id=1)


def test_rewrites_download_path_to_statdownload(bandcamp):
    bandcamp.request.return_value = "var _statDL_result = { result: 'ok'};"
    original_url = "https://p4.bcbits.com/download/track/abc?sig=xyz&id=1"

    result = bandcamp.check_download_stat(_item(), original_url)

    requested_url = bandcamp.request.call_args[0][1]
    assert "/statdownload/" in requested_url
    assert "/download/" not in requested_url
    assert bandcamp.request.call_args.kwargs["as_raw"] is True
    assert result == original_url


def test_leaves_non_download_paths_unchanged(bandcamp):
    bandcamp.request.return_value = "var _statDL_result = { result: 'ok'};"
    original_url = "https://p4.bcbits.com/somethingelse/track/abc?sig=xyz"

    bandcamp.check_download_stat(_item(), original_url)

    requested_url = bandcamp.request.call_args[0][1]
    assert "/somethingelse/" in requested_url


def test_returns_updated_url_from_stat_response(bandcamp):
    bandcamp.request.return_value = '{"download_url":"https://example.com/updated"}'
    original_url = "https://p4.bcbits.com/download/track/abc?sig=xyz"

    result = bandcamp.check_download_stat(_item(), original_url)

    assert result == "https://example.com/updated"
