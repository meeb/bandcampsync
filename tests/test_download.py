from pathlib import Path

from bandcampsync.download import _is_expired_download_page


def _load_fixture(name):
    html_path = Path(__file__).resolve().parent / "data" / name
    return html_path.read_text(encoding="utf-8", errors="ignore")


def test_expired_download_page():
    html = _load_fixture("download-expired.html")
    assert _is_expired_download_page(html) is True


def test_non_expired_download_page():
    html = _load_fixture("download-choose-format.html")
    assert _is_expired_download_page(html) is False
