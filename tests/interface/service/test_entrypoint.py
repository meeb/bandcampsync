"""Tests for bandcampsync.interface.service.entrypoint."""

import threading
from datetime import date
from unittest.mock import patch

import pytest

from bandcampsync.interface.service import entrypoint
from bandcampsync.interface.service.entrypoint import (
    CatchShutdownSignal,
    main,
    parse_bool,
    parse_until_date,
)

_ENV_KEYS = [
    "TZ",
    "COOKIES_FILE",
    "IGNORES_FILE",
    "DIRECTORY",
    "FORMAT",
    "IGNORE",
    "RUN_DAILY_AT",
    "EXIT_AFTER_RUN",
    "TEMP_DIR",
    "NOTIFY_URL",
    "UNTIL_DATE",
    "DRY_RUN",
    "MAX_RETRIES",
    "RETRY_WAIT",
    "CONCURRENCY",
    "SKIP_ITEM_INDEX",
    "SYNC_IGNORE_FILE",
    "SKIP_HIDDEN",
    "HTTP_PORT",
]


def _set_env(monkeypatch, tmp_path, **overrides):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("identity=test")
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    env = {
        "COOKIES_FILE": str(cookies_file),
        "DIRECTORY": str(download_dir),
        "EXIT_AFTER_RUN": "1",
    }
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return {"cookies_file": cookies_file, "download_dir": download_dir}


def test_parse_bool_recognizes_truthy_strings():
    for value in ("1", "true", "True", "yes", "on", "  yes  "):
        assert parse_bool(value) is True


def test_parse_bool_treats_everything_else_as_false():
    for value in ("0", "false", "no", "off", ""):
        assert parse_bool(value) is False


def test_parse_until_date_returns_none_for_empty_string():
    assert parse_until_date("") is None
    assert parse_until_date("   ") is None


def test_parse_until_date_parses_iso_date():
    assert parse_until_date("2026-02-06") == date(2026, 2, 6)


def test_parse_until_date_raises_on_invalid_format():
    with pytest.raises(ValueError, match="UNTIL_DATE"):
        parse_until_date("not-a-date")


def test_catch_shutdown_signal_sets_flag_and_wakes_event():
    wake_event = threading.Event()
    with patch.object(entrypoint.signal, "signal"):
        catcher = CatchShutdownSignal(wake_event)
        catcher.got_exit_signal(2, None)

    assert catcher.shutdown is True
    assert wake_event.is_set()


def test_main_raises_when_cookies_file_missing(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, COOKIES_FILE=str(tmp_path / "missing.txt"))

    with pytest.raises(ValueError, match="Cookies file does not exist"):
        main()


def test_main_raises_when_directory_missing(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, DIRECTORY=str(tmp_path / "missing-dir"))

    with pytest.raises(ValueError, match="Directory does not exist"):
        main()


def test_main_raises_when_temp_dir_missing(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, TEMP_DIR=str(tmp_path / "missing-temp"))

    with pytest.raises(ValueError, match="Temporary directory does not exist"):
        main()


def test_main_raises_on_invalid_timezone(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, TZ="Not/A_Zone")

    with pytest.raises(ValueError, match="valid timezone"):
        main()


def test_main_raises_when_run_daily_at_out_of_range(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, RUN_DAILY_AT="24")

    with pytest.raises(ValueError, match="RUN_DAILY_AT"):
        main()


def test_main_exit_after_run_skips_http_server_and_runs_sync(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, EXIT_AFTER_RUN="1")

    with (
        patch.object(entrypoint, "run_scheduled_sync") as mock_run_sync,
        patch.object(entrypoint, "start_http_server") as mock_start_http,
        patch.object(entrypoint.signal, "signal"),
    ):
        main()

    mock_start_http.assert_not_called()
    mock_run_sync.assert_called_once()
    assert mock_run_sync.call_args[0][3] is True


def test_main_starts_http_server_when_not_exiting_after_run(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, EXIT_AFTER_RUN="0")

    with (
        patch.object(entrypoint, "run_scheduled_sync") as mock_run_sync,
        patch.object(entrypoint, "start_http_server") as mock_start_http,
        patch.object(entrypoint.signal, "signal"),
    ):
        main()

    mock_start_http.assert_called_once()
    assert mock_start_http.call_args[0][0] == 8080
    mock_run_sync.assert_called_once()
    assert mock_run_sync.call_args[0][3] is False


def test_main_builds_options_from_env_vars(tmp_path, monkeypatch):
    paths = _set_env(
        monkeypatch,
        tmp_path,
        FORMAT="mp3-320",
        DRY_RUN="1",
        CONCURRENCY="4",
        MAX_RETRIES="7",
        RETRY_WAIT="2",
    )

    with (
        patch.object(entrypoint, "run_scheduled_sync") as mock_run_sync,
        patch.object(entrypoint, "start_http_server"),
        patch.object(entrypoint.signal, "signal"),
    ):
        main()

    options = mock_run_sync.call_args[0][0]
    assert options.cookies == "identity=test"
    assert options.dir_path == paths["download_dir"].resolve()
    assert options.media_format == "mp3-320"
    assert options.dry_run is True
    assert options.concurrency == 4
    assert options.max_retries == 7
    assert options.retry_wait == 2


def test_main_falls_back_to_default_on_unparseable_max_retries(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path, MAX_RETRIES="not-a-number")

    with (
        patch.object(entrypoint, "run_scheduled_sync") as mock_run_sync,
        patch.object(entrypoint, "start_http_server"),
        patch.object(entrypoint.signal, "signal"),
    ):
        main()

    options = mock_run_sync.call_args[0][0]
    assert options.max_retries == 3


def test_main_swallows_keyboard_interrupt_from_run_scheduled_sync(tmp_path, monkeypatch):
    _set_env(monkeypatch, tmp_path)

    with (
        patch.object(entrypoint, "run_scheduled_sync", side_effect=KeyboardInterrupt),
        patch.object(entrypoint, "start_http_server"),
        patch.object(entrypoint.signal, "signal"),
    ):
        main()  # must not raise
