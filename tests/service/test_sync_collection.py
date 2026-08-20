"""Tests for bandcampsync.service.sync_collection.

Uses importlib to get the real module object - see test_maybe_notify.py's
docstring for why a plain import doesn't work here (sync_collection.py
contains a function of the same name, re-exported by service/__init__.py,
which shadows the submodule attribute on the package).
"""

import importlib
import json
from unittest.mock import Mock, patch

from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.domain.sync import ItemSyncResult
from bandcampsync.domain.sync.checkpoint import state_file_path
from bandcampsync.service.sync_collection import sync_collection

_module = importlib.import_module("bandcampsync.service.sync_collection")


def _options(tmp_path, **overrides):
    defaults = {
        "cookies": "identity=test",
        "dir_path": tmp_path,
        "media_format": "flac",
        "temp_dir_root": tmp_path,
        "ign_file_path": None,
        "ign_patterns": "",
        "notify_url": None,
    }
    defaults.update(overrides)
    return BandcampSyncOptions(**defaults)


def _mock_bandcamp(purchases=None, collection_items=None):
    instance = Mock()
    instance.purchases = purchases or []
    instance.collection_items = collection_items or []
    instance.verify_authentication.return_value = True
    instance.load_purchases.return_value = True
    return instance


def test_no_purchases_returns_clean_outcome(tmp_path):
    bandcamp = _mock_bandcamp()
    with patch.object(_module, "Bandcamp", return_value=bandcamp):
        outcome = sync_collection(_options(tmp_path))

    assert outcome.new_items_downloaded is False
    assert outcome.errors == []
    assert outcome.had_errors is False


def test_aggregates_downloaded_flag_across_items(tmp_path):
    item = Mock(item_id=1, token="t1", purchased=None)
    bandcamp = _mock_bandcamp(purchases=[item])
    results = [ItemSyncResult(downloaded=True, show_id_file_warning=False)]

    with (
        patch.object(_module, "Bandcamp", return_value=bandcamp),
        patch.object(_module, "sync_all_items", return_value=results),
    ):
        outcome = sync_collection(_options(tmp_path))

    assert outcome.new_items_downloaded is True


def test_dry_run_does_not_write_checkpoint(tmp_path):
    item = Mock(item_id=1, token="t1", purchased=None)
    bandcamp = _mock_bandcamp(purchases=[item])

    with patch.object(_module, "Bandcamp", return_value=bandcamp):
        sync_collection(_options(tmp_path, dry_run=True))

    assert not state_file_path(tmp_path).exists()


def test_writes_checkpoint_after_successful_sync(tmp_path):
    item = Mock(item_id=1, token="new-token", purchased=None)
    bandcamp = _mock_bandcamp(purchases=[item])

    with patch.object(_module, "Bandcamp", return_value=bandcamp):
        sync_collection(_options(tmp_path))

    state = json.loads(state_file_path(tmp_path).read_text())
    assert state["last_seen_token"] == "new-token"


def test_errors_prevent_checkpoint_write(tmp_path):
    item = Mock(item_id=1, token="new-token", purchased=None)
    bandcamp = _mock_bandcamp(purchases=[item])
    results = [ItemSyncResult(downloaded=False, show_id_file_warning=False)]

    def fake_sync_all_items(items, ctx, record_error, concurrency):
        record_error("boom")
        return results

    with (
        patch.object(_module, "Bandcamp", return_value=bandcamp),
        patch.object(_module, "sync_all_items", side_effect=fake_sync_all_items),
    ):
        outcome = sync_collection(_options(tmp_path))

    assert outcome.had_errors is True
    assert not state_file_path(tmp_path).exists()


def test_checkpoint_present_skips_initial_local_media_index(tmp_path):
    state_file_path(tmp_path).write_text(json.dumps({"last_seen_token": "checkpoint-token"}))
    bandcamp = _mock_bandcamp()

    with (
        patch.object(_module, "Bandcamp", return_value=bandcamp),
        patch.object(_module, "LocalMedia") as mock_local_media,
    ):
        sync_collection(_options(tmp_path))

    assert mock_local_media.call_args.kwargs["index_on_init"] is False


def test_no_checkpoint_indexes_local_media(tmp_path):
    bandcamp = _mock_bandcamp()

    with (
        patch.object(_module, "Bandcamp", return_value=bandcamp),
        patch.object(_module, "LocalMedia") as mock_local_media,
    ):
        sync_collection(_options(tmp_path))

    assert mock_local_media.call_args.kwargs["index_on_init"] is True
