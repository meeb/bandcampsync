"""Tests for bandcampsync.service.authenticate_and_load_collection."""

from datetime import date

from bandcampsync.domain.collection import PurchaseDateParser
from bandcampsync.service.authenticate_and_load_collection import (
    authenticate_and_load_collection,
)


def test_builds_authenticates_and_loads_via_the_factory(mocker, sync_options_factory):
    bandcamp = mocker.Mock()
    bandcamp_factory = mocker.Mock(return_value=bandcamp)
    options = sync_options_factory(cookies="identity=abc")

    result = authenticate_and_load_collection(
        bandcamp_factory, options, PurchaseDateParser(), checkpoint_token=None
    )

    bandcamp_factory.assert_called_once_with("identity=abc")
    bandcamp.verify_authentication.assert_called_once()
    bandcamp.load_purchases.assert_called_once()
    assert result is bandcamp


def test_stop_when_delegates_to_should_stop_loading_purchase(
    mocker, sync_options_factory, bandcamp_item_factory
):
    bandcamp = mocker.Mock()
    options = sync_options_factory(until_date=date(2026, 1, 1))
    item = bandcamp_item_factory(purchased="01 Jan 2025 00:00:00 GMT")

    authenticate_and_load_collection(
        lambda cookies: bandcamp, options, PurchaseDateParser(), checkpoint_token=None
    )

    stop_when = bandcamp.load_purchases.call_args.kwargs["stop_when"]
    assert stop_when(item) is True
