"""Tests for bandcampsync.domain.local_media_entry.index."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from bandcampsync.domain.local_media_entry import (
    clean_format,
    clean_path,
    index_local_media,
    path_for_file,
    path_for_purchase,
    read_item_id,
)
from tests.factories import make_bandcamp_item


def _item(band_name="Band", item_title="Item", folder_suffix=""):
    return make_bandcamp_item(
        item_id=1, band_name=band_name, item_title=item_title, folder_suffix=folder_suffix
    )


def test_clean_path_strips_disallowed_punctuation():
    assert clean_path('Foo/Bar: "Baz"?') == "FooBar Baz"


def test_clean_format_strips_bitrate_suffix():
    assert clean_format("mp3-320") == "mp3"


def test_clean_format_leaves_plain_format_alone():
    assert clean_format("flac") == "flac"


def test_path_for_purchase_combines_band_and_title():
    path = path_for_purchase(Path("/media"), _item())
    assert path == Path("/media/Band/Item")


def test_path_for_purchase_includes_folder_suffix():
    path = path_for_purchase(Path("/media"), _item(folder_suffix=" [123]"))
    assert path == Path("/media/Band/Item [123]")


def test_path_for_file_cleans_the_file_name():
    assert path_for_file(Path("/media/band/item"), "track?.flac") == Path(
        "/media/band/item/track.flac"
    )


def test_read_item_id_parses_the_file_contents(tmp_path):
    id_file = tmp_path / "id.txt"
    id_file.write_text("123\n")

    assert read_item_id(id_file) == 123


def test_read_item_id_raises_on_non_numeric_contents(tmp_path):
    id_file = tmp_path / "id.txt"
    id_file.write_text("not-a-number\n")

    with pytest.raises(ValueError, match="not-a-number"):
        read_item_id(id_file)


def test_index_local_media_finds_items_with_id_files(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / "bandcamp_item_id.txt").write_text("123\n")

    index = index_local_media(tmp_path)

    assert index.by_item_id == {123: item_dir}
    assert ("Band", "Album") in index.item_names


def test_index_local_media_skips_invalid_id_files(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / "bandcamp_item_id.txt").write_text("not-an-int\n")

    with patch("bandcampsync.domain.local_media_entry.index.log.warning") as mock_warning:
        index = index_local_media(tmp_path)

    assert index.by_item_id == {}
    assert ("Band", "Album") in index.item_names
    mock_warning.assert_called_once()


def test_index_local_media_calls_on_item_discovered(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / "bandcamp_item_id.txt").write_text("123\n")
    on_item_discovered = Mock()

    index_local_media(tmp_path, on_item_discovered=on_item_discovered)

    on_item_discovered.assert_called_once_with(123, "Band", "Album")
