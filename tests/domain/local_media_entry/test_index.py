"""Tests for bandcampsync.domain.local_media_entry.index."""

from pathlib import Path

import pytest

from bandcampsync.domain.local_media_entry import (
    clean_format,
    clean_path,
    index_local_media,
    path_for_file,
    path_for_purchase,
    read_item_id,
)


def test_clean_path_strips_disallowed_punctuation():
    assert clean_path('Foo/Bar: "Baz"?') == "FooBar Baz"


def test_clean_format_strips_bitrate_suffix():
    assert clean_format("mp3-320") == "mp3"


def test_clean_format_leaves_plain_format_alone():
    assert clean_format("flac") == "flac"


def test_path_for_purchase_combines_band_and_title(bandcamp_item_factory):
    item = bandcamp_item_factory(band_name="Band", item_title="Item")
    path = path_for_purchase(Path("/media"), item)
    assert path == Path("/media/Band/Item")


def test_path_for_purchase_includes_folder_suffix(bandcamp_item_factory):
    item = bandcamp_item_factory(band_name="Band", item_title="Item", folder_suffix=" [123]")
    path = path_for_purchase(Path("/media"), item)
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


def test_index_local_media_skips_invalid_id_files(tmp_path, mocker):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / "bandcamp_item_id.txt").write_text("not-an-int\n")
    mock_warning = mocker.patch("bandcampsync.domain.local_media_entry.index.log.warning")

    index = index_local_media(tmp_path)

    assert index.by_item_id == {}
    assert ("Band", "Album") in index.item_names
    mock_warning.assert_called_once()


def test_index_local_media_calls_on_item_discovered(tmp_path, mocker):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / "bandcamp_item_id.txt").write_text("123\n")
    on_item_discovered = mocker.Mock()

    index_local_media(tmp_path, on_item_discovered=on_item_discovered)

    on_item_discovered.assert_called_once_with(123, "Band", "Album")
