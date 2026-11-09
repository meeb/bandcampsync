"""Tests for Syncer's sync_item functionality and retry logic."""

import asyncio
import shutil
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZIP_STORED, ZipFile
import pytest
from curl_cffi import CurlError, requests
from bandcampsync.sync import Syncer
from bandcampsync.options import BandcampSyncOptions
from bandcampsync.bandcamp import BandcampDownloadUnavailable, BandcampError


@pytest.fixture
def mock_bandcamp():
    with patch("bandcampsync.sync.Bandcamp") as mock_class:
        mock_instance = Mock()
        mock_instance.purchases = []
        mock_instance.collection_items = []
        mock_instance.verify_authentication.return_value = True
        mock_instance.load_purchases.return_value = True
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def syncer(mock_bandcamp, tmp_path):
    # We need to mock asyncio.run(self.sync_items()) because it's called in __init__
    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
            max_retries=2,
            retry_wait=0,
        )
        s = Syncer(options, auto_run=True)
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


def test_sync_item_does_not_retry_unavailable_download(syncer, mock_bandcamp):
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        download_url="http://example.com/download",
    )

    mock_bandcamp.get_download_file_url.side_effect = BandcampDownloadUnavailable(
        "No downloads listed"
    )

    with patch("bandcampsync.sync.time.sleep") as mock_sleep:
        result = syncer.sync_item(item)

    assert result is False
    assert syncer.had_sync_errors is False
    assert mock_bandcamp.get_download_file_url.call_count == 1
    mock_sleep.assert_not_called()


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


def test_sync_item_album_audio_file_success(syncer, mock_bandcamp, tmp_path):
    item = Mock(
        is_preorder=False,
        band_name="Mala x Magugu",
        item_title="MILITANT DON",
        item_id=188280431,
        item_type="album",
        url_hints={"slug": "militant-don"},
        download_url="http://example.com/download",
    )

    mock_bandcamp.get_download_file_url.return_value = "http://example.com/file"
    mock_bandcamp.check_download_stat.return_value = "http://example.com/file_ok"

    with (
        patch(
            "bandcampsync.sync.download_file",
            return_value="audio/mpeg",
        ),
        patch("bandcampsync.sync.is_zip_file", return_value=False),
        patch("bandcampsync.sync.copy_file") as mock_copy,
    ):
        result = syncer.sync_item(item, encoding="mp3-320")

    assert result is True
    assert syncer.new_items_downloaded is True
    args, _ = mock_copy.call_args
    assert "militant-don.mp3" in str(args[1])


def test_sync_item_uses_encoding_parameter(syncer, mock_bandcamp):
    """sync_item uses the encoding kwarg, not self.media_format, when provided."""
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        folder_suffix="",
    )
    mock_bandcamp.get_download_file_url.side_effect = BandcampError(
        "stop after first call"
    )

    syncer.sync_item(item, encoding="mp3-320")

    _, kwargs = mock_bandcamp.get_download_file_url.call_args
    assert kwargs["encoding"] == "mp3-320"


def test_sync_item_falls_back_to_media_format_when_no_encoding(syncer, mock_bandcamp):
    """When encoding=None, self.media_format is used as the encoding."""
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        folder_suffix="",
    )
    mock_bandcamp.get_download_file_url.side_effect = BandcampError(
        "stop after first call"
    )

    syncer.sync_item(item)  # no encoding kwarg

    _, kwargs = mock_bandcamp.get_download_file_url.call_args
    assert kwargs["encoding"] == syncer.media_format  # "flac" from fixture


def test_sync_item_continues_if_writing_item_id_fails(syncer, mock_bandcamp):
    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="TrackTitle",
        item_id="",
        item_type="track",
        url_hints={"slug": "track-slug"},
        download_url="http://example.com/download",
    )

    mock_bandcamp.get_download_file_url.return_value = "http://example.com/file"
    mock_bandcamp.check_download_stat.return_value = "http://example.com/file_ok"

    with (
        patch("bandcampsync.sync.download_file"),
        patch("bandcampsync.sync.is_zip_file", return_value=False),
        patch("bandcampsync.sync.copy_file"),
        patch.object(
            syncer.local_media,
            "write_bandcamp_id",
            side_effect=ValueError("bad item id"),
        ) as mock_write_id,
        patch("bandcampsync.sync.log.error") as mock_log_error,
    ):
        result = syncer.sync_item(item)

        assert result is True
        assert syncer.new_items_downloaded is True
        assert syncer.had_sync_errors is True
        assert syncer.sync_errors
        mock_write_id.assert_called_once()
        assert "Failed to write bandcamp item id" in mock_log_error.call_args[0][0]


def test_sync_item_dry_run_no_side_effects(mock_bandcamp, tmp_path):
    with patch("bandcampsync.sync.asyncio.run") as mock_run:
        options = BandcampSyncOptions(
            cookies="identity=test",
            dir_path=tmp_path,
            media_format="flac",
            temp_dir_root=tmp_path,
            ign_file_path=None,
            ign_patterns="",
            notify_url=None,
            dry_run=True,
        )
        syncer = Syncer(options, auto_run=True)
        if mock_run.called:
            coro = mock_run.call_args[0][0]
            coro.close()

    item = Mock(
        is_preorder=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        folder_suffix="",
        download_url="http://example.com/download",
    )

    with patch("bandcampsync.sync.download_file") as mock_download:
        result = syncer.sync_item(item)

    assert result is False
    assert syncer.new_items_downloaded is False
    assert not mock_download.called


def _download_item(mock_bandcamp):
    mock_bandcamp.get_download_file_url.return_value = "http://example.com/file"
    mock_bandcamp.check_download_stat.return_value = "http://example.com/file_ok"
    return Mock(
        is_preorder=False,
        hidden=False,
        band_name="Artist",
        item_title="Album",
        item_id=1,
        item_type="album",
        url_hints={"slug": "album"},
        folder_suffix="",
        download_url="http://example.com/download",
    )


def _write_zip(url, target, **kwargs):
    with ZipFile(target, "w") as archive:
        archive.writestr("track1.flac", "one")
        archive.writestr("track2.flac", "two")
    target.flush()
    return "application/zip"


def _assert_not_marked_as_downloaded(syncer, mock_add, album_dir):
    assert syncer.new_items_downloaded is False
    assert syncer.had_sync_errors is True
    mock_add.assert_not_called()
    assert not (album_dir / "bandcamp_item_id.txt").exists()


@pytest.mark.parametrize("use_ignore_file", [True, False])
def test_failed_move_does_not_mark_item_downloaded(
    syncer, mock_bandcamp, tmp_path, use_ignore_file
):
    item = _download_item(mock_bandcamp)
    syncer.ign_file_path = tmp_path / "ignores.txt" if use_ignore_file else None
    with (
        patch("bandcampsync.sync.download_file", side_effect=_write_zip),
        patch("bandcampsync.sync.move_file", side_effect=OSError("disk full")) as move,
        patch.object(syncer.ignores, "add") as mock_add,
    ):
        result = syncer.sync_item(item)

    assert result is False
    assert move.call_count == 1
    _assert_not_marked_as_downloaded(syncer, mock_add, tmp_path / "Artist" / "Album")


@pytest.mark.parametrize("use_ignore_file", [True, False])
def test_failed_copy_does_not_mark_item_downloaded(
    syncer, mock_bandcamp, tmp_path, use_ignore_file
):
    item = _download_item(mock_bandcamp)
    item.item_type = "track"
    syncer.ign_file_path = tmp_path / "ignores.txt" if use_ignore_file else None
    with (
        patch("bandcampsync.sync.download_file", return_value="audio/flac"),
        patch("bandcampsync.sync.copy_file", side_effect=OSError("disk full")),
        patch.object(syncer.ignores, "add") as mock_add,
    ):
        result = syncer.sync_item(item)

    assert result is False
    _assert_not_marked_as_downloaded(syncer, mock_add, tmp_path / "Artist" / "Album")


def test_item_is_downloaded_again_after_failed_move(syncer, mock_bandcamp, tmp_path):
    item = _download_item(mock_bandcamp)
    album_dir = tmp_path / "Artist" / "Album"
    real_move = shutil.move

    def fail_on_second_file(src, dst):
        if Path(src).name == "track2.flac":
            raise OSError("disk full")
        return real_move(src, dst)

    with patch("bandcampsync.sync.download_file", side_effect=_write_zip):
        with patch("bandcampsync.sync.move_file", side_effect=fail_on_second_file):
            assert syncer.sync_item(item) is False
        assert syncer.sync_item(item) is True

    assert (album_dir / "track1.flac").read_text() == "one"
    assert (album_dir / "track2.flac").read_text() == "two"
    assert (album_dir / "bandcamp_item_id.txt").read_text().strip() == "1"


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.ConnectionError("connection refused"),
        requests.exceptions.DNSError("could not resolve host"),
        requests.exceptions.IncompleteRead("bytes missing"),
        CurlError("other curl failure"),
    ],
)
def test_network_error_is_retried(syncer, mock_bandcamp, tmp_path, error):
    item = _download_item(mock_bandcamp)
    errors = [error]

    def fail_then_download(url, target, **kwargs):
        if errors:
            raise errors.pop()
        return _write_zip(url, target)

    with (
        patch("bandcampsync.sync.download_file", side_effect=fail_then_download),
        patch("bandcampsync.sync.time.sleep") as mock_sleep,
    ):
        assert syncer.sync_item(item) is True

    mock_sleep.assert_called_once_with(syncer.retry_wait)
    assert syncer.had_sync_errors is False
    assert (tmp_path / "Artist" / "Album" / "track2.flac").read_text() == "two"


def test_network_error_on_every_attempt_does_not_stop_sync(
    syncer, mock_bandcamp, tmp_path
):
    failing = _download_item(mock_bandcamp)
    working = _download_item(mock_bandcamp)
    working.item_id = 2
    working.item_title = "Second Album"
    mock_bandcamp.purchases = [failing, working]
    error = requests.exceptions.ConnectionError("connection refused")

    def fail_first_item(url, target, **kwargs):
        if mock_download.call_count <= syncer.max_retries:
            raise error
        return _write_zip(url, target)

    with (
        patch(
            "bandcampsync.sync.download_file", side_effect=fail_first_item
        ) as mock_download,
        patch("bandcampsync.sync.time.sleep"),
    ):
        asyncio.run(syncer.sync_items())

    assert mock_download.call_count == syncer.max_retries + 1
    assert len(syncer.sync_errors) == 1
    assert "connection refused" in syncer.sync_errors[0]
    assert not (tmp_path / "Artist" / "Album").exists()
    assert (tmp_path / "Artist" / "Second Album" / "track1.flac").exists()
    assert not syncer.state_file_path.exists()


def _write_corrupt_zip(url, target, **kwargs):
    """A valid zip index, but a track fails its checksum when it's extracted."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_STORED) as archive:
        archive.writestr("track1.flac", "one")
    target.write(buffer.getvalue().replace(b"one", b"bad", 1))
    target.flush()
    return "application/zip"


def test_corrupt_zip_is_retried(syncer, mock_bandcamp, tmp_path):
    item = _download_item(mock_bandcamp)
    downloads = [_write_corrupt_zip, _write_zip]

    def next_download(url, target, **kwargs):
        return downloads.pop(0)(url, target, **kwargs)

    with (
        patch("bandcampsync.sync.download_file", side_effect=next_download),
        patch("bandcampsync.sync.time.sleep") as mock_sleep,
    ):
        assert syncer.sync_item(item) is True

    mock_sleep.assert_called_once_with(syncer.retry_wait)
    assert syncer.had_sync_errors is False
    assert (tmp_path / "Artist" / "Album" / "track2.flac").read_text() == "two"


def test_corrupt_zip_on_every_attempt_records_an_error(syncer, mock_bandcamp, tmp_path):
    item = _download_item(mock_bandcamp)
    with (
        patch(
            "bandcampsync.sync.download_file", side_effect=_write_corrupt_zip
        ) as mock_download,
        patch("bandcampsync.sync.time.sleep"),
    ):
        assert syncer.sync_item(item) is False

    assert mock_download.call_count == syncer.max_retries
    assert "decompress" in syncer.sync_errors[0]
    assert not (tmp_path / "Artist" / "Album" / "bandcamp_item_id.txt").exists()


def test_local_file_error_skips_only_that_item(syncer, mock_bandcamp, tmp_path):
    failing = _download_item(mock_bandcamp)
    working = _download_item(mock_bandcamp)
    working.item_id = 2
    working.item_title = "Second Album"
    mock_bandcamp.purchases = [failing, working]

    def disk_full_on_first_item(url, target, **kwargs):
        if mock_download.call_count == 1:
            raise OSError(28, "No space left on device")
        return _write_zip(url, target)

    with patch(
        "bandcampsync.sync.download_file", side_effect=disk_full_on_first_item
    ) as mock_download:
        asyncio.run(syncer.sync_items())

    assert mock_download.call_count == 2
    assert len(syncer.sync_errors) == 1
    assert "No space left on device" in syncer.sync_errors[0]
    assert (tmp_path / "Artist" / "Second Album" / "track1.flac").exists()
    assert not syncer.state_file_path.exists()


def test_download_uses_current_browser_profile(syncer, mock_bandcamp):
    item = _download_item(mock_bandcamp)
    mock_bandcamp.browser_profile = "firefox155"
    with patch(
        "bandcampsync.sync.download_file", side_effect=_write_zip
    ) as mock_download:
        assert syncer.sync_item(item) is True

    assert mock_download.call_args.kwargs["impersonate"] == "firefox155"


def test_single_track_without_url_hints_uses_title(syncer, mock_bandcamp, tmp_path):
    item = _download_item(mock_bandcamp)
    item.item_type = "track"
    item.url_hints = None
    with (
        patch("bandcampsync.sync.download_file", return_value="audio/flac"),
        patch("bandcampsync.sync.copy_file") as mock_copy,
    ):
        assert syncer.sync_item(item) is True

    assert mock_copy.call_args.args[1].name == "Album.flac"
