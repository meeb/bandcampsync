from unittest.mock import Mock, patch

import pytest

from bandcampsync.media import LocalMedia


def _create_local_media(tmp_path, skip_item_index=False):
    ignore_ids = {1} if skip_item_index else set()
    return LocalMedia(
        media_dir=tmp_path,
        ignores=Mock(ids=ignore_ids),
        skip_item_index=skip_item_index,
        sync_ignore_file=False,
    )


def test_index_skips_empty_item_id_file(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("")

    with patch("bandcampsync.media.log.warning") as mock_warning:
        local_media = _create_local_media(tmp_path)

    assert local_media.media == {}
    assert ("Band", "Album") in local_media.item_names
    assert local_media.is_locally_downloaded(Mock(item_id=123), item_dir)
    mock_warning.assert_called_once()
    assert "Skipping invalid item index file" in mock_warning.call_args[0][0]


def test_index_skips_non_numeric_item_id_file(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("not-an-int\n")

    with patch("bandcampsync.media.log.warning") as mock_warning:
        local_media = _create_local_media(tmp_path)

    assert local_media.media == {}
    assert ("Band", "Album") in local_media.item_names
    assert local_media.is_locally_downloaded(Mock(item_id=123), item_dir)
    mock_warning.assert_called_once()
    assert "Skipping invalid item index file" in mock_warning.call_args[0][0]


def test_index_loads_valid_item_id_file(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("123\n")

    local_media = _create_local_media(tmp_path)

    assert local_media.media == {123: item_dir}
    assert ("Band", "Album") in local_media.item_names


def test_write_bandcamp_id_skips_empty_item_id(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    local_media = _create_local_media(tmp_path, skip_item_index=True)

    with patch("bandcampsync.media.NamedTemporaryFile") as mock_tempfile:
        with pytest.raises(ValueError):
            local_media.write_bandcamp_id(Mock(item_id=""), item_dir)

    assert not (item_dir / LocalMedia.ITEM_INDEX_FILENAME).exists()
    mock_tempfile.assert_not_called()


def test_write_bandcamp_id_preserves_existing_file_on_write_failure(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    outfile = item_dir / LocalMedia.ITEM_INDEX_FILENAME
    outfile.write_text("123\n")
    local_media = _create_local_media(tmp_path, skip_item_index=True)

    mock_tempfile = Mock()
    mock_tempfile.__enter__ = Mock(return_value=Mock(name="/tmp/bad-temp"))
    mock_tempfile.__exit__ = Mock(return_value=False)
    mock_tempfile.__enter__.return_value.name = str(item_dir / "tmp-id-file")
    mock_tempfile.__enter__.return_value.write.side_effect = OSError("disk full")

    with patch("bandcampsync.media.NamedTemporaryFile", return_value=mock_tempfile):
        with pytest.raises(OSError):
            local_media.write_bandcamp_id(Mock(item_id=456), item_dir)

    assert outfile.read_text() == "123\n"
