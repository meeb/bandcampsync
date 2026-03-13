from unittest.mock import Mock, patch

from bandcampsync.media import LocalMedia


def _create_local_media(tmp_path):
    return LocalMedia(
        media_dir=tmp_path,
        ignores=Mock(ids=set()),
        skip_item_index=False,
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
