"""Tests for bandcampsync.domain.file_transfer.archive."""

from pathlib import Path
from zipfile import ZipFile

from bandcampsync.domain.file_transfer.archive import extract_zip_archive, is_zip_archive


def _make_zip(path: Path, contents: dict[str, str]) -> Path:
    with ZipFile(path, "w") as z:
        for name, data in contents.items():
            z.writestr(name, data)
    return path


def test_is_zip_archive_true_for_a_real_zip(tmp_path):
    archive = _make_zip(tmp_path / "download.zip", {"track1.flac": "data"})

    assert is_zip_archive(archive) is True


def test_is_zip_archive_false_for_a_non_zip_file(tmp_path):
    not_a_zip = tmp_path / "download.flac"
    not_a_zip.write_bytes(b"fLaC not a zip")

    assert is_zip_archive(not_a_zip) is False


def test_is_zip_archive_false_for_a_missing_file(tmp_path):
    assert is_zip_archive(tmp_path / "missing.zip") is False


def test_extract_zip_archive_writes_out_every_member(tmp_path):
    archive = _make_zip(tmp_path / "download.zip", {"track1.flac": "one", "track2.flac": "two"})
    destination = tmp_path / "extracted"
    destination.mkdir()

    result = extract_zip_archive(archive, destination)

    assert result is True
    assert (destination / "track1.flac").read_text() == "one"
    assert (destination / "track2.flac").read_text() == "two"
