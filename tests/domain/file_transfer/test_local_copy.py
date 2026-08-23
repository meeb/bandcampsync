"""Tests for bandcampsync.domain.file_transfer.local_copy."""

from bandcampsync.domain.file_transfer.local_copy import copy_file, move_file


def test_copy_file_leaves_source_in_place(tmp_path):
    src = tmp_path / "source.flac"
    src.write_text("audio data")
    dst = tmp_path / "dest.flac"

    copy_file(src, dst)

    assert dst.read_text() == "audio data"
    assert src.exists()


def test_move_file_removes_source(tmp_path):
    src = tmp_path / "source.flac"
    src.write_text("audio data")
    dst = tmp_path / "dest.flac"

    move_file(src, dst)

    assert dst.read_text() == "audio data"
    assert not src.exists()
