"""Tests for Syncer."""

import json
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch
import pytest
from bandcampsync.bandcamp import Bandcamp
from bandcampsync.sync import Syncer
from bandcampsync.options import BandcampSyncOptions


@pytest.fixture
def mock_bandcamp():
    with patch("bandcampsync.sync.Bandcamp") as mock_class:
        mock_instance = Mock(purchases=[], collection_items=[])
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def syncer_minimal(mock_bandcamp, tmp_path):
    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        s = Syncer(options, auto_run=True)
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()
    return s


def test_skips_preorder(mock_bandcamp, tmp_path):
    mock_bandcamp.purchases = [
        Mock(is_preorder=True, band_name="Band", item_title="Album", item_id=1)
    ]

    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        syncer = Syncer(options, auto_run=True)
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
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        syncer = Syncer(options, auto_run=True)
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    assert not syncer.new_items_downloaded


def test_ignore_pattern(mock_bandcamp, tmp_path):
    mock_bandcamp.purchases = [
        Mock(is_preorder=False, band_name="Ignore_This", item_title="Album", item_id=1)
    ]

    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="ignore_this",
            notify_url=None,
        )
        syncer = Syncer(options, auto_run=True)
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
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
            until_date=datetime.strptime("2026-02-06", "%Y-%m-%d").date(),
        )
        syncer = Syncer(options, auto_run=True)
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
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        syncer = Syncer(options, auto_run=True)
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
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
        )
        Syncer(options, auto_run=True)
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


def _checkpoint_state(syncer, tmp_path):
    syncer._save_collection_checkpoint()
    return json.loads((tmp_path / syncer.STATE_FILENAME).read_text())


def test_checkpoint_stays_behind_oldest_preorder(syncer_minimal, tmp_path):
    syncer_minimal.bandcamp.collection_items = [
        Mock(token="newest", is_preorder=False),
        Mock(token="new-preorder", is_preorder=True),
        Mock(token="middle", is_preorder=False),
        Mock(token="old-preorder", is_preorder=True),
        Mock(token="older", is_preorder=False, item_id=7, purchased="date"),
        Mock(token="oldest", is_preorder=False),
    ]

    state = _checkpoint_state(syncer_minimal, tmp_path)

    assert state["last_seen_token"] == "older"
    assert state["last_seen_item_id"] == 7
    assert state["has_unreleased_preorder"] is True


def test_checkpoint_is_cleared_when_preorder_is_oldest_item(syncer_minimal, tmp_path):
    syncer_minimal.bandcamp.collection_items = [
        Mock(token="newest", is_preorder=False),
        Mock(token="preorder", is_preorder=True),
    ]

    state = _checkpoint_state(syncer_minimal, tmp_path)

    assert state["last_seen_token"] is None
    assert state["has_unreleased_preorder"] is True
    assert syncer_minimal._load_collection_checkpoint() is None


def test_checkpoint_uses_newest_item_without_preorders(syncer_minimal, tmp_path):
    syncer_minimal.bandcamp.collection_items = [
        Mock(token="newest", is_preorder=False, item_id=7, purchased="date"),
        Mock(token="older", is_preorder=False),
    ]

    state = _checkpoint_state(syncer_minimal, tmp_path)

    assert state["last_seen_token"] == "newest"
    assert state["has_unreleased_preorder"] is False


def test_checkpoint_with_preorder_indexes_local_media(mock_bandcamp, tmp_path):
    state = {"last_seen_token": "older", "has_unreleased_preorder": True}
    (tmp_path / Syncer.STATE_FILENAME).write_text(json.dumps(state))
    album = tmp_path / "Band" / "Renamed Album"
    album.mkdir(parents=True)
    (album / "bandcamp_item_id.txt").write_text("5\n")

    syncer = Syncer(
        BandcampSyncOptions(cookies="identity=test", dir_path=tmp_path),
        auto_run=False,
    )

    assert syncer.collection_checkpoint_token == "older"
    assert syncer.local_media.media == {5: album}


def _collection_item(item_id, token, **extra):
    return {
        "item_id": item_id,
        "band_name": "Band",
        "item_title": f"Album {item_id}",
        "item_type": "track",
        "token": token,
        "is_preorder": False,
        "sale_item_type": "t",
        "sale_item_id": item_id,
        "url_hints": {"slug": f"album-{item_id}"},
        "folder_suffix": "",
        "purchased": "01 Jan 2026 00:00:00 GMT",
        **extra,
    }


def _run_collection_sync(tmp_path, items, downloadable):
    """Runs a real Syncer and Bandcamp, returning the IDs of the items downloaded."""
    pages = [
        {
            "items": items,
            "redownload_urls": {
                f"t{i}": f"https://bandcamp.test/{i}" for i in downloadable
            },
        },
    ]

    def fake_verify(self):
        self.user_id = 1
        self.is_authenticated = True
        return True

    def fake_request(self, *args, **kwargs):
        return pages.pop(0) if pages else {"items": [], "redownload_urls": {}}

    downloaded = []

    def fake_download_url(self, item, encoding="flac"):
        downloaded.append(item.item_id)
        return "https://bandcamp.test/file"

    with (
        patch.object(Bandcamp, "verify_authentication", fake_verify),
        patch.object(Bandcamp, "_request", fake_request),
        patch.object(Bandcamp, "get_download_file_url", fake_download_url),
        patch.object(
            Bandcamp, "check_download_stat", return_value="https://bandcamp.test/file"
        ),
        patch("bandcampsync.sync.download_file", return_value="audio/flac"),
    ):
        syncer = Syncer(
            BandcampSyncOptions(cookies="identity=test", dir_path=tmp_path),
            auto_run=False,
        )
        asyncio.run(syncer.sync_items())
    assert syncer.sync_errors == []
    return downloaded


@pytest.mark.parametrize("preorder_has_url", [True, False])
def test_preorder_is_downloaded_after_release(tmp_path, preorder_has_url):
    older = _collection_item(1, "older")
    newest = _collection_item(3, "newest")
    preorder = _collection_item(2, "preorder", is_preorder=True)
    released = _collection_item(2, "preorder")

    def collection(middle):
        return [dict(newest), dict(middle), dict(older)]

    first_urls = [1, 2, 3] if preorder_has_url else [1, 3]
    assert _run_collection_sync(tmp_path, collection(preorder), first_urls) == [3, 1]
    # Still unreleased, everything else is already downloaded
    assert _run_collection_sync(tmp_path, collection(preorder), first_urls) == []
    # Now released, only the preorder is new
    assert _run_collection_sync(tmp_path, collection(released), [1, 2, 3]) == [2]

    state = json.loads((tmp_path / Syncer.STATE_FILENAME).read_text())
    assert state["last_seen_token"] == "newest"
    assert state["has_unreleased_preorder"] is False
    # Nothing newer, so the run stops at the checkpoint and nothing is downloaded
    assert _run_collection_sync(tmp_path, collection(released), [1, 2, 3]) == []
