"""Tests for bandcampsync.interface.http.trigger_server."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from bandcampsync.domain import LogTail, SyncState
from bandcampsync.interface.http.trigger_server import start_http_server


@pytest.fixture
def server_url() -> Iterator[tuple[str, SyncState, threading.Event]]:
    state = SyncState()
    log_tail = LogTail()
    wake_event = threading.Event()
    server = start_http_server(0, state, log_tail, wake_event, host="127.0.0.1")
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}", state, wake_event
    finally:
        server.shutdown()


def _get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_root_serves_html_page(server_url: tuple[str, SyncState, threading.Event]) -> None:
    base_url, _, _ = server_url
    with urllib.request.urlopen(base_url + "/") as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
    assert "Sync now" in body


def test_status_reports_idle_by_default(
    server_url: tuple[str, SyncState, threading.Event],
) -> None:
    base_url, _, _ = server_url
    status, body = _get(base_url + "/status")
    assert status == 200
    assert body["status"] == "idle"
    assert body["log_tail"] == []


def test_sync_sets_the_wake_event(server_url: tuple[str, SyncState, threading.Event]) -> None:
    base_url, _, wake_event = server_url
    status, body = _post(base_url + "/sync")
    assert status == 202
    assert body["message"] == "sync requested"
    assert wake_event.is_set()


def test_sync_while_running_does_not_re_trigger(
    server_url: tuple[str, SyncState, threading.Event],
) -> None:
    base_url, state, wake_event = server_url
    state.mark_running()
    status, body = _post(base_url + "/sync")
    assert status == 200
    assert body["message"] == "sync already in progress"
    assert not wake_event.is_set()


def test_unknown_path_is_404(server_url: tuple[str, SyncState, threading.Event]) -> None:
    base_url, _, _ = server_url
    status, body = _get(base_url + "/nope")
    assert status == 404
    assert body["error"] == "not found"
