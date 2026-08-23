"""Tests for bandcampsync.interface.bandcamp.expired_download_page."""

from pathlib import Path

from bandcampsync.interface.bandcamp.expired_download_page import is_expired_download_page


def _load_fixture(name: str) -> str:
    html_path = Path(__file__).resolve().parent / "data" / name
    return html_path.read_text(encoding="utf-8", errors="ignore")


def test_expired_download_page():
    html = _load_fixture("download-expired.html")
    assert is_expired_download_page(html) is True


def test_non_expired_download_page():
    html = _load_fixture("download-choose-format.html")
    assert is_expired_download_page(html) is False
