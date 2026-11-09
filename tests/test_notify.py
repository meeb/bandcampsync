"""Tests for NotifyURL."""

import socket
from unittest.mock import Mock, patch

import pytest
from curl_cffi import CurlError, requests

from bandcampsync.notify import NotifyURL
from bandcampsync.options import BandcampSyncOptions
from bandcampsync.sync import Syncer


def _unused_local_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{sock.getsockname()[1]}/"


@pytest.mark.parametrize("target", ["{url}", "GET {url} - -", "POST {url} - -"])
def test_unreachable_url_returns_false(target):
    notify = NotifyURL(target.format(url=_unused_local_url()))

    assert notify.valid is True
    assert notify.notify() is False


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.ConnectionError("connection refused"),
        requests.exceptions.Timeout("timed out"),
        CurlError("other curl failure"),
    ],
)
def test_request_errors_return_false(error):
    with patch("bandcampsync.notify.requests.get", side_effect=error):
        assert NotifyURL("http://example.com/").notify() is False


def test_failed_notify_does_not_raise_from_syncer(tmp_path):
    with patch("bandcampsync.sync.Bandcamp") as mock_class:
        mock_class.return_value = Mock(purchases=[], collection_items=[])
        syncer = Syncer(
            BandcampSyncOptions(
                cookies="identity=test",
                dir_path=tmp_path,
                notify_url=_unused_local_url(),
            ),
            auto_run=False,
        )
    syncer.new_items_downloaded = True

    syncer.notify()


def test_successful_notify_returns_true():
    response = Mock(status_code=204)
    with patch("bandcampsync.notify.requests.get", return_value=response):
        assert NotifyURL("http://example.com/").notify() is True
