"""Tests for bandcampsync.service.authenticate_and_load_collection."""

from datetime import date
from unittest.mock import Mock

from bandcampsync.domain.collection import PurchaseDateParser
from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.service.authenticate_and_load_collection import (
    authenticate_and_load_collection,
)


def _options(**overrides):
    defaults = {
        "cookies": "identity=test",
        "dir_path": "/media",
        "media_format": "flac",
        "temp_dir_root": None,
        "ign_file_path": None,
        "ign_patterns": "",
        "notify_url": None,
    }
    defaults.update(overrides)
    return BandcampSyncOptions(**defaults)


def test_builds_authenticates_and_loads_via_the_factory():
    bandcamp = Mock()
    bandcamp_factory = Mock(return_value=bandcamp)
    options = _options(cookies="identity=abc")

    result = authenticate_and_load_collection(
        bandcamp_factory, options, PurchaseDateParser(), checkpoint_token=None
    )

    bandcamp_factory.assert_called_once_with("identity=abc")
    bandcamp.verify_authentication.assert_called_once()
    bandcamp.load_purchases.assert_called_once()
    assert result is bandcamp


def test_stop_when_delegates_to_should_stop_loading_purchase():
    bandcamp = Mock()
    options = _options(until_date=date(2026, 1, 1))
    item = Mock(token=None, purchased="01 Jan 2025 00:00:00 GMT")

    authenticate_and_load_collection(
        lambda cookies: bandcamp, options, PurchaseDateParser(), checkpoint_token=None
    )

    stop_when = bandcamp.load_purchases.call_args.kwargs["stop_when"]
    assert stop_when(item) is True
