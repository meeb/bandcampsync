from pathlib import Path
from unittest.mock import Mock, patch

from bandcampsync.domain.ignore_entry import IgnoreRules
from bandcampsync.domain.media import LocalMedia


def _create_local_media(
    tmp_path, skip_item_index=False, index_on_init=True, sync_ignore_file=False, ignore_rules=None
):
    if ignore_rules is None:
        ignore_rules = Mock(ids={1} if skip_item_index else set())
    return LocalMedia(
        media_dir=tmp_path,
        ignore_rules=ignore_rules,
        ignore_file_writer=Mock(),
        skip_item_index=skip_item_index,
        sync_ignore_file=sync_ignore_file,
        index_on_init=index_on_init,
    )


def test_index_skips_empty_item_id_file(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("")

    with patch("bandcampsync.domain.media.log.warning") as mock_warning:
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

    with patch("bandcampsync.domain.media.log.warning") as mock_warning:
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


def test_lazy_local_download_check_when_not_indexed(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("123\n")

    local_media = _create_local_media(tmp_path, index_on_init=False)

    assert local_media.media == {}
    assert local_media.is_locally_downloaded(Mock(item_id=123), item_dir) is True
    assert local_media.media == {123: item_dir}


def test_lazy_local_download_check_detects_name_mismatch(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("456\n")

    local_media = _create_local_media(tmp_path, index_on_init=False)

    assert local_media.is_locally_downloaded(Mock(item_id=123), item_dir) is True
    assert local_media.media == {456: item_dir}


def test_sync_ignore_file_records_newly_discovered_items_not_already_ignored(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("123\n")
    ignore_file_writer = Mock()

    local_media = LocalMedia(
        media_dir=tmp_path,
        ignore_rules=IgnoreRules(),
        ignore_file_writer=ignore_file_writer,
        skip_item_index=False,
        sync_ignore_file=True,
    )

    assert local_media.media == {123: item_dir}
    ignore_file_writer.record.assert_called_once()
    recorded_item = ignore_file_writer.record.call_args[0][0]
    assert recorded_item.item_id == 123
    assert recorded_item.band_name == "Band"
    assert recorded_item.item_title == "Album"


def test_sync_ignore_file_skips_items_already_ignored(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / LocalMedia.ITEM_INDEX_FILENAME).write_text("123\n")
    ignore_file_writer = Mock()

    LocalMedia(
        media_dir=tmp_path,
        ignore_rules=IgnoreRules(ids=frozenset({123})),
        ignore_file_writer=ignore_file_writer,
        skip_item_index=False,
        sync_ignore_file=True,
    )

    ignore_file_writer.record.assert_not_called()


def test_sync_ignore_file_disabled_never_records():
    with_writer = Mock()

    LocalMedia(
        media_dir=Path("/nonexistent-should-not-be-walked"),
        ignore_rules=IgnoreRules(),
        ignore_file_writer=with_writer,
        skip_item_index=True,
        sync_ignore_file=False,
        index_on_init=False,
    )

    with_writer.record.assert_not_called()
