"""Tests for Syncer's sync_item functionality and retry logic."""

from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pytest
from bandcampsync.sync import Syncer
from bandcampsync.bandcamp import BandcampError
from bandcampsync.download import DownloadBadStatusCode, DownloadInvalidContentType


@pytest.fixture
def mock_bandcamp():
    with patch("bandcampsync.sync.Bandcamp") as mock_class:
        mock_instance = Mock()
        mock_instance.purchases = []
        mock_instance.verify_authentication.return_value = True
        mock_instance.load_purchases.return_value = True
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def syncer(mock_bandcamp, tmp_path):
    # We need to mock asyncio.run(self.sync_items()) because it's called in __init__
    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        s = Syncer(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=str(tmp_path),
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
            max_retries=2,
            retry_wait=0,
        )
        # The call to Syncer() triggers self.sync_items() which returns a coroutine.
        # Since asyncio.run is mocked, this coroutine is never awaited, causing a warning.
        # We can get the coroutine object from the mock call and close it.
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()
    return s


def test_sync_item_success(syncer, mock_bandcamp, tmp_path):
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        download_url="http://example.com/download",
    )

    mock_bandcamp.get_download_file_url.return_value = "http://example.com/file"
    mock_bandcamp.check_download_stat.return_value = "http://example.com/file_ok"

    with (
        patch("bandcampsync.sync.download_file") as mock_download,
        patch("bandcampsync.sync.is_zip_file", return_value=True),
        patch("bandcampsync.sync.unzip_file") as mock_unzip,
        patch("bandcampsync.sync.TemporaryDirectory") as mock_temp_dir,
    ):
        # Setup temp directory mock
        temp_dir_path = tmp_path / "temp_extract"
        temp_dir_path.mkdir()
        mock_temp_dir.return_value.__enter__.return_value = str(temp_dir_path)

        # Create a fake file in the temp directory
        (temp_dir_path / "track1.flac").write_text("audio data")

        with patch("bandcampsync.sync.move_file") as mock_move:
            result = syncer.sync_item(item)

            assert result is True
            assert syncer.new_items_downloaded is True
            mock_download.assert_called_once()
            mock_unzip.assert_called_once()
            mock_move.assert_called_once()


def test_sync_item_retries_and_succeeds(syncer, mock_bandcamp, tmp_path):
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        download_url="http://example.com/download",
    )

    # Fail once, then succeed
    mock_bandcamp.get_download_file_url.side_effect = [
        BandcampError("first fail"),
        "http://example.com/file",
    ]
    mock_bandcamp.check_download_stat.return_value = "http://example.com/file_ok"

    with (
        patch("bandcampsync.sync.download_file"),
        patch("bandcampsync.sync.is_zip_file", return_value=True),
        patch("bandcampsync.sync.unzip_file"),
        patch("bandcampsync.sync.TemporaryDirectory") as mock_temp_dir,
        patch("bandcampsync.sync.time.sleep") as mock_sleep,
    ):
        temp_dir_path = tmp_path / "temp_extract"
        temp_dir_path.mkdir()
        mock_temp_dir.return_value.__enter__.return_value = str(temp_dir_path)
        (temp_dir_path / "track1.flac").write_text("audio data")

        with patch("bandcampsync.sync.move_file"):
            result = syncer.sync_item(item)

            assert result is True
            assert mock_bandcamp.get_download_file_url.call_count == 2
            mock_sleep.assert_called_once_with(syncer.retry_wait)


def test_sync_item_fails_after_max_retries(syncer, mock_bandcamp):
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        download_url="http://example.com/download",
    )

    # Always fail
    mock_bandcamp.get_download_file_url.side_effect = BandcampError("persistent fail")

    with patch("bandcampsync.sync.time.sleep") as mock_sleep:
        result = syncer.sync_item(item)

        assert result is False
        assert mock_bandcamp.get_download_file_url.call_count == syncer.max_retries
        assert mock_sleep.call_count == syncer.max_retries - 1


def test_sync_item_track_success(syncer, mock_bandcamp, tmp_path):
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="TrackTitle",
        item_id=1,
        item_type="track",
        url_hints={"slug": "track-slug"},
        download_url="http://example.com/download",
    )

    mock_bandcamp.get_download_file_url.return_value = "http://example.com/file"
    mock_bandcamp.check_download_stat.return_value = "http://example.com/file_ok"

    with (
        patch("bandcampsync.sync.download_file"),
        patch("bandcampsync.sync.is_zip_file", return_value=False),
        patch("bandcampsync.sync.copy_file") as mock_copy,
    ):
        result = syncer.sync_item(item)

        assert result is True
        assert syncer.new_items_downloaded is True
        # Check if copy_file was called with expected destination name (using slug)
        args, _ = mock_copy.call_args
        assert "track-slug.flac" in str(args[1])
