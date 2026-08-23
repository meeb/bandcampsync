"""Tests for bandcampsync.service.sync_collection.

Uses importlib to get the real module object - see test_maybe_notify.py's
docstring for why a plain import doesn't work here (sync_collection.py
contains a function of the same name, re-exported by service/__init__.py,
which shadows the submodule attribute on the package).
"""

import importlib
import json

from bandcampsync.domain.collection import PurchaseDownloadResult
from bandcampsync.domain.collection.checkpoint import state_file_path
from bandcampsync.service.sync_collection import sync_collection_with

_module = importlib.import_module("bandcampsync.service.sync_collection")


def _mock_bandcamp(mocker, purchases=None, collection_items=None):
    instance = mocker.Mock()
    instance.purchases = purchases or []
    instance.collection_items = collection_items or []
    instance.verify_authentication.return_value = True
    instance.load_purchases.return_value = True
    return instance


def test_no_purchases_returns_clean_outcome(mocker, sync_options_factory):
    bandcamp = _mock_bandcamp(mocker)
    outcome = sync_collection_with(
        sync_options_factory(), bandcamp_factory=lambda cookies: bandcamp
    )

    assert outcome.new_items_downloaded is False
    assert outcome.errors == []
    assert outcome.had_errors is False


def test_aggregates_downloaded_flag_across_items(
    mocker, sync_options_factory, bandcamp_item_factory
):
    item = bandcamp_item_factory(item_id=1, token="t1")
    bandcamp = _mock_bandcamp(mocker, purchases=[item])
    results = [PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)]
    mocker.patch.object(_module, "sync_all_items", return_value=results)

    outcome = sync_collection_with(
        sync_options_factory(), bandcamp_factory=lambda cookies: bandcamp
    )

    assert outcome.new_items_downloaded is True


def test_dry_run_does_not_write_checkpoint(
    mocker, sync_options_factory, bandcamp_item_factory, tmp_path
):
    item = bandcamp_item_factory(item_id=1, token="t1")
    bandcamp = _mock_bandcamp(mocker, purchases=[item])

    sync_collection_with(
        sync_options_factory(dry_run=True), bandcamp_factory=lambda cookies: bandcamp
    )

    assert not state_file_path(tmp_path).exists()


def test_writes_checkpoint_after_successful_sync(
    mocker, sync_options_factory, bandcamp_item_factory, tmp_path
):
    item = bandcamp_item_factory(item_id=1, token="new-token")
    bandcamp = _mock_bandcamp(mocker, purchases=[item])
    results = [PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)]
    mocker.patch.object(_module, "sync_all_items", return_value=results)

    sync_collection_with(sync_options_factory(), bandcamp_factory=lambda cookies: bandcamp)

    state = json.loads(state_file_path(tmp_path).read_text())
    assert state["last_seen_token"] == "new-token"


def test_errors_prevent_checkpoint_write(
    mocker, sync_options_factory, bandcamp_item_factory, tmp_path
):
    item = bandcamp_item_factory(item_id=1, token="new-token")
    bandcamp = _mock_bandcamp(mocker, purchases=[item])
    results = [PurchaseDownloadResult(downloaded=False, show_id_file_warning=False)]

    def fake_sync_all_items(items, ctx, record_error, concurrency):
        record_error("boom")
        return results

    mocker.patch.object(_module, "sync_all_items", side_effect=fake_sync_all_items)

    outcome = sync_collection_with(
        sync_options_factory(), bandcamp_factory=lambda cookies: bandcamp
    )

    assert outcome.had_errors is True
    assert not state_file_path(tmp_path).exists()
