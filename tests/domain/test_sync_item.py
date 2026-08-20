"""Tests for bandcampsync.domain.sync.item.sync_item."""

from unittest.mock import Mock, patch

from bandcampsync.domain.bandcamp import BandcampDownloadUnavailable, BandcampError
from bandcampsync.domain.sync.item import ItemSyncContext, sync_item


def _make_ctx(tmp_path, **overrides):
    bandcamp = Mock()
    local_media = Mock()
    local_media.get_path_for_purchase.return_value = tmp_path / "Artist" / "Album"
    local_media.is_locally_downloaded.return_value = False
    local_media.clean_format.side_effect = lambda fmt: fmt.split("-")[0] if "-" in fmt else fmt
    local_media.get_path_for_file.side_effect = lambda local_path, name: local_path / name
    ignores = Mock()
    ignores.is_ignored.return_value = False
    defaults = {
        "bandcamp": bandcamp,
        "local_media": local_media,
        "ignores": ignores,
        "media_format": "flac",
        "temp_dir_root": tmp_path,
        "max_retries": 2,
        "retry_wait": 0,
        "dry_run": False,
        "skip_hidden": False,
        "ign_file_path": None,
    }
    defaults.update(overrides)
    return ItemSyncContext(**defaults)


def _errors():
    collected: list[str] = []
    return collected, collected.append


def _item(**kwargs):
    defaults = {
        "is_preorder": False,
        "band_name": "Artist",
        "item_title": "Album",
        "item_id": 1,
        "item_type": "album",
        "hidden": False,
        "download_url": "http://example.com/download",
    }
    defaults.update(kwargs)
    return Mock(**defaults)


def test_skips_hidden_item(tmp_path):
    ctx = _make_ctx(tmp_path, skip_hidden=True)
    _, record_error = _errors()

    result = sync_item(_item(hidden=True), ctx, record_error)

    assert result.downloaded is False
    ctx.ignores.is_ignored.assert_not_called()


def test_skips_ignored_item(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.ignores.is_ignored.return_value = True
    ctx.local_media.is_locally_downloaded.return_value = True
    _, record_error = _errors()

    result = sync_item(_item(), ctx, record_error)

    assert result.downloaded is False
    assert result.show_id_file_warning is True


def test_skips_preorder(tmp_path):
    ctx = _make_ctx(tmp_path)
    _, record_error = _errors()

    result = sync_item(_item(is_preorder=True), ctx, record_error)

    assert result.downloaded is False


def test_skips_already_downloaded(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.local_media.is_locally_downloaded.return_value = True
    _, record_error = _errors()

    result = sync_item(_item(), ctx, record_error)

    assert result.downloaded is False


def test_dry_run_no_side_effects(tmp_path):
    ctx = _make_ctx(tmp_path, dry_run=True)
    _, record_error = _errors()

    with patch("bandcampsync.domain.sync.item.download_file") as mock_download:
        result = sync_item(_item(), ctx, record_error)

    assert result.downloaded is False
    assert not mock_download.called


def test_sync_item_success(tmp_path):
    ctx = _make_ctx(tmp_path)
    _, record_error = _errors()
    ctx.bandcamp.get_download_file_url.return_value = "http://example.com/file"
    ctx.bandcamp.check_download_stat.return_value = "http://example.com/file_ok"

    with (
        patch("bandcampsync.domain.sync.item.download_file") as mock_download,
        patch("bandcampsync.domain.sync.item.is_zip_file", return_value=True),
        patch("bandcampsync.domain.sync.item.unzip_file") as mock_unzip,
        patch("bandcampsync.domain.sync.item.TemporaryDirectory") as mock_temp_dir,
    ):
        temp_dir_path = tmp_path / "temp_extract"
        temp_dir_path.mkdir()
        mock_temp_dir.return_value.__enter__.return_value = str(temp_dir_path)
        (temp_dir_path / "track1.flac").write_text("audio data")

        with patch("bandcampsync.domain.sync.item.move_file") as mock_move:
            result = sync_item(_item(), ctx, record_error)

    assert result.downloaded is True
    mock_download.assert_called_once()
    mock_unzip.assert_called_once()
    mock_move.assert_called_once()


def test_sync_item_retries_and_succeeds(tmp_path):
    ctx = _make_ctx(tmp_path)
    _, record_error = _errors()
    ctx.bandcamp.get_download_file_url.side_effect = [
        BandcampError("first fail"),
        "http://example.com/file",
    ]
    ctx.bandcamp.check_download_stat.return_value = "http://example.com/file_ok"

    with (
        patch("bandcampsync.domain.sync.item.download_file"),
        patch("bandcampsync.domain.sync.item.is_zip_file", return_value=True),
        patch("bandcampsync.domain.sync.item.unzip_file"),
        patch("bandcampsync.domain.sync.item.TemporaryDirectory") as mock_temp_dir,
        patch("bandcampsync.domain.sync.item.time.sleep") as mock_sleep,
    ):
        temp_dir_path = tmp_path / "temp_extract"
        temp_dir_path.mkdir()
        mock_temp_dir.return_value.__enter__.return_value = str(temp_dir_path)
        (temp_dir_path / "track1.flac").write_text("audio data")

        with patch("bandcampsync.domain.sync.item.move_file"):
            result = sync_item(_item(), ctx, record_error)

    assert result.downloaded is True
    assert ctx.bandcamp.get_download_file_url.call_count == 2
    mock_sleep.assert_called_once_with(ctx.retry_wait)


def test_sync_item_fails_after_max_retries(tmp_path):
    ctx = _make_ctx(tmp_path)
    errors, record_error = _errors()
    ctx.bandcamp.get_download_file_url.side_effect = BandcampError("persistent fail")

    with patch("bandcampsync.domain.sync.item.time.sleep") as mock_sleep:
        result = sync_item(_item(), ctx, record_error)

    assert result.downloaded is False
    assert ctx.bandcamp.get_download_file_url.call_count == ctx.max_retries
    assert mock_sleep.call_count == ctx.max_retries - 1
    assert errors


def test_does_not_retry_unavailable_download(tmp_path):
    ctx = _make_ctx(tmp_path)
    errors, record_error = _errors()
    ctx.bandcamp.get_download_file_url.side_effect = BandcampDownloadUnavailable(
        "No downloads listed"
    )

    with patch("bandcampsync.domain.sync.item.time.sleep") as mock_sleep:
        result = sync_item(_item(), ctx, record_error)

    assert result.downloaded is False
    assert not errors
    assert ctx.bandcamp.get_download_file_url.call_count == 1
    mock_sleep.assert_not_called()


def test_sync_item_track_success(tmp_path):
    ctx = _make_ctx(tmp_path)
    _, record_error = _errors()
    ctx.bandcamp.get_download_file_url.return_value = "http://example.com/file"
    ctx.bandcamp.check_download_stat.return_value = "http://example.com/file_ok"
    item = _item(item_title="TrackTitle", item_type="track", url_hints={"slug": "track-slug"})

    with (
        patch("bandcampsync.domain.sync.item.download_file"),
        patch("bandcampsync.domain.sync.item.is_zip_file", return_value=False),
        patch("bandcampsync.domain.sync.item.copy_file") as mock_copy,
    ):
        result = sync_item(item, ctx, record_error)

    assert result.downloaded is True
    args, _ = mock_copy.call_args
    assert "track-slug.flac" in str(args[1])


def test_sync_item_album_audio_file_success(tmp_path):
    ctx = _make_ctx(tmp_path)
    _, record_error = _errors()
    ctx.bandcamp.get_download_file_url.return_value = "http://example.com/file"
    ctx.bandcamp.check_download_stat.return_value = "http://example.com/file_ok"
    item = _item(
        band_name="Mala x Magugu",
        item_title="MILITANT DON",
        item_id=188280431,
        url_hints={"slug": "militant-don"},
    )

    with (
        patch("bandcampsync.domain.sync.item.download_file", return_value="audio/mpeg"),
        patch("bandcampsync.domain.sync.item.is_zip_file", return_value=False),
        patch("bandcampsync.domain.sync.item.copy_file") as mock_copy,
    ):
        result = sync_item(item, ctx, record_error, encoding="mp3-320")

    assert result.downloaded is True
    args, _ = mock_copy.call_args
    assert "militant-don.mp3" in str(args[1])


def test_uses_encoding_parameter_not_context_media_format(tmp_path):
    ctx = _make_ctx(tmp_path, media_format="flac")
    _, record_error = _errors()
    ctx.bandcamp.get_download_file_url.side_effect = BandcampError("stop after first call")

    sync_item(_item(), ctx, record_error, encoding="mp3-320")

    _, kwargs = ctx.bandcamp.get_download_file_url.call_args
    assert kwargs["encoding"] == "mp3-320"


def test_falls_back_to_context_media_format_when_no_encoding(tmp_path):
    ctx = _make_ctx(tmp_path, media_format="flac")
    _, record_error = _errors()
    ctx.bandcamp.get_download_file_url.side_effect = BandcampError("stop after first call")

    sync_item(_item(), ctx, record_error)

    _, kwargs = ctx.bandcamp.get_download_file_url.call_args
    assert kwargs["encoding"] == "flac"


def test_continues_if_writing_item_id_fails(tmp_path):
    ctx = _make_ctx(tmp_path)
    errors, record_error = _errors()
    ctx.bandcamp.get_download_file_url.return_value = "http://example.com/file"
    ctx.bandcamp.check_download_stat.return_value = "http://example.com/file_ok"
    ctx.local_media.write_bandcamp_id.side_effect = ValueError("bad item id")
    item = _item(item_title="TrackTitle", item_id="", item_type="track", url_hints={"slug": "x"})

    with (
        patch("bandcampsync.domain.sync.item.download_file"),
        patch("bandcampsync.domain.sync.item.is_zip_file", return_value=False),
        patch("bandcampsync.domain.sync.item.copy_file"),
    ):
        result = sync_item(item, ctx, record_error)

    assert result.downloaded is True
    assert len(errors) == 1
    assert "Failed to write bandcamp item id" in errors[0]


def test_ign_file_path_set_adds_to_ignores_instead_of_writing_id(tmp_path):
    ctx = _make_ctx(tmp_path, ign_file_path=tmp_path / "ignores.txt")
    _, record_error = _errors()
    ctx.bandcamp.get_download_file_url.return_value = "http://example.com/file"
    ctx.bandcamp.check_download_stat.return_value = "http://example.com/file_ok"
    item = _item(item_type="track", url_hints={"slug": "x"})

    with (
        patch("bandcampsync.domain.sync.item.download_file"),
        patch("bandcampsync.domain.sync.item.is_zip_file", return_value=False),
        patch("bandcampsync.domain.sync.item.copy_file"),
    ):
        result = sync_item(item, ctx, record_error)

    assert result.downloaded is True
    ctx.ignores.add.assert_called_once_with(item)
    ctx.local_media.write_bandcamp_id.assert_not_called()
