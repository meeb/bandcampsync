"""Tests for Syncer."""

from unittest.mock import Mock, patch
import pytest
from bandcampsync.sync import Syncer


@pytest.fixture
def mock_bandcamp():
    with patch("bandcampsync.sync.Bandcamp") as mock_class:
        mock_instance = Mock(purchases=[])
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
