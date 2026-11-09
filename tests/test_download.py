import importlib.util
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from curl_cffi import requests

import bandcampsync.download
from bandcampsync.download import (
    DownloadCorrupt,
    _fetch_html_body,
    _is_expired_download_page,
    _read_html_body,
    is_zip_file,
    mask_sig,
    temporary_download_path,
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


SIGNED_URL = "https://bandcamp.test/download?id=1&sig=secretsig&token=secrettoken&ts=2"


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            SIGNED_URL,
            "https://bandcamp.test/download?id=1&sig=[masked]&token=[masked]&ts=2",
        ),
        ("https://bandcamp.test/?sig=secret", "https://bandcamp.test/?sig=[masked]"),
        (
            "https://bandcamp.test/?token=secret&id=1",
            "https://bandcamp.test/?token=[masked]&id=1",
        ),
        (
            "https://bandcamp.test/?fsig=keep&id=1",
            "https://bandcamp.test/?fsig=keep&id=1",
        ),
        ("https://bandcamp.test/", "https://bandcamp.test/"),
    ],
)
def test_mask_sig(url, expected):
    assert mask_sig(url) == expected


def test_failed_fetch_masks_url_in_log(caplog):
    error = requests.exceptions.ConnectionError("connection refused")
    with patch("bandcampsync.download.requests.get", side_effect=error):
        assert _fetch_html_body(SIGNED_URL, "firefox155") == ""

    assert "Failed to fetch HTML body" in caplog.text
    assert "secret" not in caplog.text


@pytest.mark.parametrize("attribute", ["text", "content"])
def test_failed_read_masks_url_in_log(caplog, attribute):
    error = requests.exceptions.ConnectionError("connection reset")
    response = Mock(url=SIGNED_URL, text="", content=b"")
    setattr(type(response), attribute, PropertyMock(side_effect=error))
    with patch("bandcampsync.download._fetch_html_body", return_value=""):
        assert _read_html_body(response, "firefox155") == ""

    assert "HTML body for" in caplog.text
    assert "secret" not in caplog.text


def test_unzip_shortens_names_the_filesystem_cannot_use(tmp_path):
    path = tmp_path / "download.zip"
    long_name = "\u28ce" * 100
    with ZipFile(path, "w") as archive:
        archive.writestr(f"{long_name}.flac", "audio")
        archive.writestr(f"{long_name}/track.flac", "nested")
        archive.writestr("cover.jpg", "art")

    assert unzip_file(path, tmp_path / "out") is True

    extracted = {
        file.relative_to(tmp_path / "out").as_posix(): file.read_text()
        for file in (tmp_path / "out").rglob("*")
        if file.is_file()
    }
    assert extracted["cover.jpg"] == "art"
    assert sorted(extracted.values()) == ["art", "audio", "nested"]
    assert any(name.endswith(".flac") and name.count("/") == 0 for name in extracted)
    assert any(name.endswith("/track.flac") for name in extracted)


def test_unzip_does_not_write_outside_the_target_directory(tmp_path):
    path = tmp_path / "download.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("../outside.flac", "bad")

    unzip_file(path, tmp_path / "out")

    assert not (tmp_path / "outside.flac").exists()
    assert (tmp_path / "out" / "outside.flac").read_text() == "bad"


def test_temporary_download_path_is_closed_and_removed(tmp_path):
    with temporary_download_path(tmp_path) as path:
        # Opening it again by name is what fails on Windows if it's still open
        path.write_bytes(b"data")
        assert path.read_bytes() == b"data"

    assert not path.exists()


def test_temporary_download_path_is_removed_after_an_error(tmp_path):
    with pytest.raises(ValueError):
        with temporary_download_path(tmp_path) as path:
            raise ValueError("failed")

    assert not path.exists()
