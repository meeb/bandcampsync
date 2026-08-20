"""Tests for bandcampsync.service.sync_all_items.

Uses importlib to get the real module object - see test_maybe_notify.py's
docstring for why a plain import doesn't work here (sync_all_items.py
contains a function of the same name, re-exported by service/__init__.py,
which shadows the submodule attribute on the package).
"""

import asyncio
import importlib
from unittest.mock import Mock, patch

from bandcampsync.domain.sync import ItemSyncResult
from bandcampsync.service.sync_all_items import sync_all_items

_module = importlib.import_module("bandcampsync.service.sync_all_items")


def test_sequential_calls_sync_item_once_per_item():
    items = [Mock(item_id=1), Mock(item_id=2), Mock(item_id=3)]
    ctx = Mock()
    record_error = Mock()

    with patch.object(
        _module,
        "sync_item",
        side_effect=lambda item, c, re: ItemSyncResult(downloaded=True, show_id_file_warning=False),
    ) as mock_sync_item:
        results = asyncio.run(sync_all_items(items, ctx, record_error, concurrency=1))

    assert mock_sync_item.call_count == 3
    assert all(r.downloaded for r in results)


def test_concurrent_syncs_all_items_and_preserves_order():
    items = [Mock(item_id=i) for i in range(5)]
    ctx = Mock()
    record_error = Mock()

    def fake_sync_item(item, c, re):
        return ItemSyncResult(downloaded=item.item_id % 2 == 0, show_id_file_warning=False)

    with patch.object(_module, "sync_item", side_effect=fake_sync_item):
        results = asyncio.run(sync_all_items(items, ctx, record_error, concurrency=2))

    assert [r.downloaded for r in results] == [True, False, True, False, True]


def test_empty_items_returns_empty():
    results = asyncio.run(sync_all_items([], Mock(), Mock(), concurrency=1))
    assert results == []
