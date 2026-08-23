"""Tests for bandcampsync.domain.local_media_entry.actions."""

from unittest.mock import Mock, patch

import pytest

from bandcampsync.domain.local_media_entry import write_bandcamp_id


def test_write_bandcamp_id_skips_empty_item_id(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)

    with (
        patch("bandcampsync.domain.local_media_entry.actions.NamedTemporaryFile") as mock_tempfile,
        pytest.raises(ValueError),
    ):
        write_bandcamp_id(Mock(item_id=""), item_dir)

    assert not (item_dir / "bandcamp_item_id.txt").exists()
    mock_tempfile.assert_not_called()


def test_write_bandcamp_id_writes_the_file(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)

    write_bandcamp_id(Mock(item_id=456), item_dir)

    assert (item_dir / "bandcamp_item_id.txt").read_text() == "456\n"


def test_write_bandcamp_id_preserves_existing_file_on_write_failure(tmp_path):
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    outfile = item_dir / "bandcamp_item_id.txt"
    outfile.write_text("123\n")

    mock_tempfile = Mock()
    mock_tempfile.__enter__ = Mock(return_value=Mock(name="/tmp/bad-temp"))
    mock_tempfile.__exit__ = Mock(return_value=False)
    mock_tempfile.__enter__.return_value.name = str(item_dir / "tmp-id-file")
    mock_tempfile.__enter__.return_value.write.side_effect = OSError("disk full")

    with (
        patch(
            "bandcampsync.domain.local_media_entry.actions.NamedTemporaryFile",
            return_value=mock_tempfile,
        ),
        pytest.raises(OSError),
    ):
        write_bandcamp_id(Mock(item_id=456), item_dir)

    assert outfile.read_text() == "123\n"
