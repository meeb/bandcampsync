import importlib.util
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

import bandcampsync.download
from bandcampsync.download import (
    DownloadCorrupt,
    _is_expired_download_page,
    is_zip_file,
    unzip_file,
)


def _load_fixture(name):
    html_path = Path(__file__).resolve().parent / "data" / name
    return html_path.read_text(encoding="utf-8", errors="ignore")


def test_expired_download_page():
    html = _load_fixture("download-expired.html")
    assert _is_expired_download_page(html) is True


def test_non_expired_download_page():
    html = _load_fixture("download-choose-format.html")
    assert _is_expired_download_page(html) is False


def _corrupt_zip(tmp_path, compression):
    path = tmp_path / "download.zip"
    content = b"track data " * 1000
    with ZipFile(path, "w", compression) as archive:
        archive.writestr("track.flac", content)
    data = bytearray(path.read_bytes())
    # Damage the middle of the track's data, leaving the zip index intact
    middle = len(data) // 3
    data[middle : middle + 8] = b"\xff" * 8
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("compression", [ZIP_STORED, ZIP_DEFLATED])
def test_unzip_corrupt_file_raises_download_corrupt(tmp_path, compression):
    path = _corrupt_zip(tmp_path, compression)

    assert is_zip_file(path) is True
    with pytest.raises(DownloadCorrupt):
        unzip_file(path, tmp_path / "out")


def test_unzip_valid_file(tmp_path):
    path = tmp_path / "download.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("track.flac", "data")

    assert unzip_file(path, tmp_path / "out") is True
    assert (tmp_path / "out" / "track.flac").read_text() == "data"


def test_module_imports_with_no_configured_profiles(monkeypatch):
    monkeypatch.setattr("bandcampsync.config.BROWSER_PROFILES", ())
    # A separate copy of the module, so reloading doesn't replace the exception classes
    spec = importlib.util.spec_from_file_location(
        "bandcampsync._download_copy", bandcampsync.download.__file__
    )

    spec.loader.exec_module(importlib.util.module_from_spec(spec))
