import os
from unittest.mock import Mock, patch

import pytest

from bandcampsync.media import LocalMedia


def _create_local_media(tmp_path, skip_item_index=False, index_on_init=True):
    ignore_ids = {1} if skip_item_index else set()
    return LocalMedia(
        media_dir=tmp_path,
        ignores=Mock(ids=ignore_ids),
        skip_item_index=skip_item_index,
        sync_ignore_file=False,
        index_on_init=index_on_init,
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


@pytest.mark.parametrize("name", ["..", ".", "", " ", " .. ", "?", "/", "../"])
def test_clean_path_never_leaves_the_media_directory(name):
    assert LocalMedia._clean_path(name) == "_"


@pytest.mark.parametrize(
    "name,expected",
    [("...", "..."), ("Band. Name", "Band. Name"), ("..Band", "..Band"), ("a/b", "ab")],
)
def test_clean_path_keeps_usable_names(name, expected):
    assert LocalMedia._clean_path(name, windows=False) == expected


def test_path_for_purchase_stays_inside_media_directory(tmp_path):
    local_media = _create_local_media(tmp_path, index_on_init=False)
    item = Mock(band_name="..", item_title="..", folder_suffix="")

    path = local_media.get_path_for_purchase(item).resolve()

    assert path == tmp_path.resolve() / "_" / "_"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Album <one> | two", "Album one  two"),
        ("Album\x01Name", "AlbumName"),
        ("Album. . ", "Album"),
        ("...", "_"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("COM1", "_COM1"),
        ("Conference", "Conference"),
        ("Normal Album", "Normal Album"),
    ],
)
def test_clean_path_on_windows(name, expected):
    assert LocalMedia._clean_path(name, windows=True) == expected


@pytest.mark.parametrize("name", ["Album <one> | two", "Album. ", "CON", "..."])
def test_clean_path_keeps_windows_only_rules_off_other_platforms(name):
    assert LocalMedia._clean_path(name, windows=False) == name


def test_paths_for_unusable_names_can_be_created(tmp_path):
    local_media = _create_local_media(tmp_path, index_on_init=False)
    item = Mock(band_name="\u28ce" * 300, item_title="\u28ce" * 300, folder_suffix="")

    path = local_media.get_path_for_purchase(item)
    path.mkdir(parents=True)
    file_path = local_media.get_path_for_file(path, "\u28ce" * 300 + ".flac")
    file_path.write_text("audio")

    assert file_path.suffix == ".flac"
    assert file_path.read_text() == "audio"


def test_folder_suffix_keeps_long_names_separate(tmp_path):
    local_media = _create_local_media(tmp_path, index_on_init=False)
    title = "\u28ce" * 300

    first = local_media.get_path_for_purchase(
        Mock(band_name="Band", item_title=title, folder_suffix=" [1]")
    )
    second = local_media.get_path_for_purchase(
        Mock(band_name="Band", item_title=title, folder_suffix=" [2]")
    )

    assert first != second


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="Requires permissions to be enforced",
)
def test_index_skips_unreadable_directories(tmp_path):
    locked = tmp_path / "lost+found"
    locked.mkdir()
    locked_album = tmp_path / "Band" / "Locked"
    locked_album.mkdir(parents=True)
    album = tmp_path / "Band" / "Album"
    album.mkdir()
    (album / LocalMedia.ITEM_INDEX_FILENAME).write_text("5\n")
    locked.chmod(0)
    locked_album.chmod(0)
    try:
        local_media = _create_local_media(tmp_path)
    finally:
        locked.chmod(0o700)
        locked_album.chmod(0o700)

    assert local_media.media == {5: album}


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="Requires permissions to be enforced",
)
def test_index_raises_if_media_directory_is_unreadable(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    media_dir.chmod(0)
    try:
        with pytest.raises(PermissionError):
            _create_local_media(media_dir)
    finally:
        media_dir.chmod(0o700)


def test_index_continues_after_id_file_error(tmp_path):
    bad = tmp_path / "Band" / "Bad"
    bad.mkdir(parents=True)
    (bad / LocalMedia.ITEM_INDEX_FILENAME).write_bytes(b"\xff\xfe")
    good = tmp_path / "Band" / "Good"
    good.mkdir()
    (good / LocalMedia.ITEM_INDEX_FILENAME).write_text("5\n")

    assert _create_local_media(tmp_path).media == {5: good}
