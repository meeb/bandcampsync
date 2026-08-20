"""Tests for bandcampsync.domain.sync.selection."""

from datetime import datetime

from bandcampsync.domain.sync.selection import (
    PurchaseDateParser,
    item_token,
    ordered_purchases,
    select_items_to_sync,
    should_stop_loading_purchase,
)


def _item(**kwargs):
    from unittest.mock import Mock

    return Mock(**kwargs)


def test_item_token_returns_none_for_missing_or_empty():
    assert item_token(_item(token=None)) is None
    assert item_token(_item(token="")) is None
    assert item_token(_item(token="abc")) == "abc"


def test_purchase_date_parser_parses_gmt_suffix():
    parser = PurchaseDateParser()
    item = _item(purchased="06 Feb 2026 19:06:47 GMT")

    dt = parser.parse(item)

    assert dt == datetime(2026, 2, 6, 19, 6, 47, tzinfo=dt.tzinfo)


def test_purchase_date_parser_warns_once_for_unparseable_dates(caplog):
    import logging

    parser = PurchaseDateParser()
    caplog.set_level(logging.WARNING, logger="sync")

    assert parser.parse(_item(purchased="not a date")) is None
    assert parser.parse(_item(purchased="also not a date")) is None

    warnings = [r for r in caplog.records if "Unable to parse purchase date" in r.message]
    assert len(warnings) == 1


def test_ordered_purchases_sorts_newest_first_when_dates_present():
    items = [
        _item(item_id=1, purchased="05 Feb 2026 12:00:00 GMT"),
        _item(item_id=2, purchased="06 Feb 2026 19:06:47 GMT"),
        _item(item_id=3, purchased="06 Feb 2026 05:00:00 GMT"),
    ]

    ordered = ordered_purchases(items, PurchaseDateParser())

    assert [item.item_id for item in ordered] == [2, 3, 1]


def test_ordered_purchases_keeps_original_order_when_no_dates():
    items = [_item(item_id=1, purchased=None), _item(item_id=2, purchased=None)]

    ordered = ordered_purchases(items, PurchaseDateParser())

    assert [item.item_id for item in ordered] == [1, 2]


def test_should_stop_loading_purchase_at_checkpoint_token():
    item = _item(token="checkpoint-token", purchased=None)

    assert should_stop_loading_purchase(item, PurchaseDateParser(), "checkpoint-token", None)
    assert not should_stop_loading_purchase(item, PurchaseDateParser(), "other-token", None)


def test_should_stop_loading_purchase_before_until_date():
    item = _item(purchased="04 Feb 2026 12:00:00 GMT", token=None)
    until_date = datetime.strptime("2026-02-06", "%Y-%m-%d").date()

    assert should_stop_loading_purchase(item, PurchaseDateParser(), None, until_date)


def test_select_items_to_sync_respects_until_date_inclusive():
    items = [
        _item(item_id=1, token=None, purchased="06 Feb 2026 19:06:47 GMT"),
        _item(item_id=2, token=None, purchased="06 Feb 2026 05:00:00 GMT"),
        _item(item_id=3, token=None, purchased="05 Feb 2026 12:00:00 GMT"),
    ]
    until_date = datetime.strptime("2026-02-06", "%Y-%m-%d").date()

    selected = select_items_to_sync(items, PurchaseDateParser(), None, until_date)

    assert [item.item_id for item in selected] == [1, 2]


def test_select_items_to_sync_stops_at_checkpoint():
    items = [
        _item(item_id=1, token="new-token", purchased="06 Feb 2026 19:06:47 GMT"),
        _item(item_id=2, token="checkpoint-token", purchased="05 Feb 2026 12:00:00 GMT"),
        _item(item_id=3, token="old-token", purchased="04 Feb 2026 12:00:00 GMT"),
    ]

    selected = select_items_to_sync(items, PurchaseDateParser(), "checkpoint-token", None)

    assert [item.item_id for item in selected] == [1]


def test_select_items_to_sync_empty_input():
    assert select_items_to_sync([], PurchaseDateParser(), None, None) == []
