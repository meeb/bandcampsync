"""Tests for Syncer."""

import json
from datetime import datetime
from unittest.mock import Mock, patch
import pytest
from bandcampsync.sync import Syncer


@pytest.fixture
def mock_bandcamp():
    with patch("bandcampsync.sync.Bandcamp") as mock_class:
        mock_instance = Mock(purchases=[], collection_items=[])
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def syncer_minimal(mock_bandcamp, tmp_path):
    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        s = Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()
    return s


def test_skips_preorder(mock_bandcamp, tmp_path):
    mock_bandcamp.purchases = [
        Mock(is_preorder=True, band_name="Band", item_title="Album", item_id=1)
    ]

    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        syncer = Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    assert not syncer.new_items_downloaded


def test_skips_already_downloaded(mock_bandcamp, tmp_path):
    (tmp_path / "Band" / "Album").mkdir(parents=True)
    (tmp_path / "Band" / "Album" / "bandcamp_item_id.txt").write_text("123\n")

    mock_bandcamp.purchases = [
        Mock(
            is_preorder=False,
            band_name="Band",
            item_title="Album",
            item_id=123,
            item_type="album",
            url_hints=None,
        )
    ]

    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        syncer = Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    assert not syncer.new_items_downloaded


def test_ignore_pattern(mock_bandcamp, tmp_path):
    mock_bandcamp.purchases = [
        Mock(is_preorder=False, band_name="Ignore_This", item_title="Album", item_id=1)
    ]

    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        syncer = Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="ignore_this",
            notify_url=None,
        )
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    assert not syncer.new_items_downloaded


def test_until_date_inclusive(mock_bandcamp, tmp_path):
    mock_bandcamp.purchases = [
        Mock(
            is_preorder=False,
            band_name="Artist A",
            item_title="Album A",
            item_id=1,
            purchased="06 Feb 2026 19:06:47 GMT",
        ),
        Mock(
            is_preorder=False,
            band_name="Artist B",
            item_title="Album B",
            item_id=2,
            purchased="06 Feb 2026 05:00:00 GMT",
        ),
        Mock(
            is_preorder=False,
            band_name="Artist C",
            item_title="Album C",
            item_id=3,
            purchased="05 Feb 2026 12:00:00 GMT",
        ),
    ]

    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        syncer = Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
            until_date=datetime.strptime("2026-02-06", "%Y-%m-%d").date(),
        )
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    selected = syncer._select_items_to_sync()
    assert [item.item_id for item in selected] == [1, 2]


def test_checkpoint_stops_selection(mock_bandcamp, tmp_path):
    state_file = tmp_path / ".bandcampsync-state.json"
    state_file.write_text(json.dumps({"last_seen_token": "checkpoint-token"}) + "\n")

    mock_bandcamp.purchases = [
        Mock(
            is_preorder=False,
            band_name="Artist A",
            item_title="Album A",
            item_id=1,
            token="new-token",
            purchased="06 Feb 2026 19:06:47 GMT",
        ),
        Mock(
            is_preorder=False,
            band_name="Artist B",
            item_title="Album B",
            item_id=2,
            token="checkpoint-token",
            purchased="05 Feb 2026 12:00:00 GMT",
        ),
        Mock(
            is_preorder=False,
            band_name="Artist C",
            item_title="Album C",
            item_id=3,
            token="old-token",
            purchased="04 Feb 2026 12:00:00 GMT",
        ),
    ]

    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        syncer = Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    selected = syncer._select_items_to_sync()
    assert [item.item_id for item in selected] == [1]


def test_checkpoint_skips_initial_local_media_index(mock_bandcamp, tmp_path):
    state_file = tmp_path / ".bandcampsync-state.json"
    state_file.write_text(json.dumps({"last_seen_token": "checkpoint-token"}) + "\n")

    with (
        patch("bandcampsync.sync.LocalMedia") as mock_local_media,
        patch("bandcampsync.sync.asyncio.run") as mock_run,
    ):
        Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    assert mock_local_media.call_args.kwargs["index_on_init"] is False


def test_writes_checkpoint_state(syncer_minimal, tmp_path):
    syncer_minimal.bandcamp.purchases = [
        Mock(token="new-token", item_id=123, purchased="06 Feb 2026 19:06:47 GMT")
    ]
    syncer_minimal._save_collection_checkpoint()

    state_file = tmp_path / ".bandcampsync-state.json"
    assert state_file.is_file()
    state = json.loads(state_file.read_text())
    assert state["last_seen_token"] == "new-token"
    assert state["last_seen_item_id"] == 123


def test_writes_checkpoint_from_newest_collection_item(syncer_minimal, tmp_path):
    syncer_minimal.bandcamp.collection_items = [
        Mock(token="physical-token", item_id=456, purchased="07 Feb 2026 19:06:47 GMT")
    ]
    syncer_minimal.bandcamp.purchases = []
    syncer_minimal._save_collection_checkpoint()

    state_file = tmp_path / ".bandcampsync-state.json"
    assert state_file.is_file()
    state = json.loads(state_file.read_text())
    assert state["last_seen_token"] == "physical-token"
    assert state["last_seen_item_id"] == 456


def test_does_not_write_checkpoint_on_errors(syncer_minimal, tmp_path):
    syncer_minimal.bandcamp.purchases = [
        Mock(token="new-token", item_id=123, purchased="06 Feb 2026 19:06:47 GMT")
    ]
    syncer_minimal.had_sync_errors = True
    syncer_minimal._save_collection_checkpoint()

    state_file = tmp_path / ".bandcampsync-state.json"
    assert not state_file.exists()


def test_logs_sync_error_summary(syncer_minimal):
    syncer_minimal._record_sync_error("first failure")
    syncer_minimal._record_sync_error("second failure")

    with patch("bandcampsync.sync.log.warning") as mock_warning:
        syncer_minimal._log_sync_error_summary()

    assert mock_warning.call_count == 3
    assert "2 error(s)" in mock_warning.call_args_list[0][0][0]
    assert "first failure" in mock_warning.call_args_list[1][0][0]
    assert "second failure" in mock_warning.call_args_list[2][0][0]
