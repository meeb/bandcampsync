"""Composition root for the sync service: reads env vars, wires up the
domain/service/interface pieces, and runs until told to stop.
"""

import logging
import os
import signal
import threading
from datetime import date, datetime
from pathlib import Path
from types import FrameType
from zoneinfo import ZoneInfo

from bandcampsync import BandcampSyncOptions, version
from bandcampsync.domain import LogTail, SyncState
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.interface.http import start_http_server
from bandcampsync.service import run_scheduled_sync

log = get_logger("service")

# Every get_logger() call in this package propagates to the root logger by
# default, so a single handler here picks up log lines from every module
# (sync, bandcamp, download, ...) without touching them individually.
log_tail = LogTail()
logging.getLogger().addHandler(log_tail)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_until_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid UNTIL_DATE: {value}") from e


class CatchShutdownSignal:
    """Tracks a shutdown request and immediately wakes the service loop's wait.

    Without waking wake_event too, a shutdown request arriving during the
    idle wait would sit unnoticed for up to a day before the loop rechecks.
    """

    def __init__(self, wake_event: threading.Event) -> None:
        self.shutdown = False
        self.wake_event = wake_event
        signal.signal(signal.SIGINT, self.got_exit_signal)
        signal.signal(signal.SIGTERM, self.got_exit_signal)

    def got_exit_signal(self, signum: int, frame: FrameType | None) -> None:
        self.shutdown = True
        self.wake_event.set()


def main() -> None:
    tz_name = os.getenv("TZ", "UTC")
    cookies_path_env = os.getenv("COOKIES_FILE", "/config/cookies.txt")
    ign_file_path_env = os.getenv("IGNORES_FILE", "/config/ignores.txt")
    dir_path_env = os.getenv("DIRECTORY", "/downloads")
    media_format_env = os.getenv("FORMAT", "flac")
    ign_patterns = os.getenv("IGNORE", "")
    run_daily_at_env = os.getenv("RUN_DAILY_AT", "3")
    exit_after_run_env = os.getenv("EXIT_AFTER_RUN", "0")
    temp_dir_env = os.getenv("TEMP_DIR", "")
    notify_url_env = os.getenv("NOTIFY_URL", "")
    until_date = parse_until_date(os.getenv("UNTIL_DATE", ""))
    dry_run = parse_bool(os.getenv("DRY_RUN", "0"))
    max_retries_env = os.getenv("MAX_RETRIES", "3")
    retry_wait_env = os.getenv("RETRY_WAIT", "5")
    concurrency_env = os.getenv("CONCURRENCY", "1")
    skip_item_index_env = os.getenv("SKIP_ITEM_INDEX", "0")
    sync_ignore_file_env = os.getenv("SYNC_IGNORE_FILE", "0")
    skip_hidden_env = os.getenv("SKIP_HIDDEN", "0")
    http_port_env = os.getenv("HTTP_PORT", "8080")

    try:
        max_retries = int(max_retries_env)
    except (ValueError, TypeError):
        max_retries = 3
    try:
        retry_wait = int(retry_wait_env)
    except (ValueError, TypeError):
        retry_wait = 5
    try:
        concurrency = int(concurrency_env)
    except (ValueError, TypeError):
        concurrency = 1
    try:
        http_port = int(http_port_env)
    except (ValueError, TypeError):
        http_port = 8080
    skip_item_index = parse_bool(skip_item_index_env)
    sync_ignore_file = parse_bool(sync_ignore_file_env)
    skip_hidden = parse_bool(skip_hidden_env)

    cookies_path = Path(cookies_path_env).resolve()
    if not cookies_path.is_file():
        raise ValueError(f"Cookies file does not exist: {cookies_path}")
    with cookies_path.open() as f:
        cookies = f.read().strip()
    log.info(f'Loaded cookies from "{cookies_path}"')

    ign_file_path = Path(ign_file_path_env).resolve()
    dir_path = Path(dir_path_env).resolve()
    if skip_item_index and not ign_file_path:
        raise ValueError(
            "SKIP_ITEM_INDEX was set, but no ignore file path was set. "
            "SKIP_ITEM_INDEX requires IGNORES_FILE"
        )
    if sync_ignore_file and not ign_file_path:
        raise ValueError(
            "SYNC_IGNORE_FILE was set, but no ignore file path was set. "
            "SYNC_IGNORE_FILE requires IGNORES_FILE"
        )
    if not dir_path.is_dir():
        raise ValueError(f"Directory does not exist: {dir_path}")

    temp_dir = None
    if temp_dir_env:
        temp_dir = Path(temp_dir_env).resolve()
        if not temp_dir.is_dir():
            raise ValueError(f"Temporary directory does not exist: {temp_dir}")

    notify_url = notify_url_env.strip() or None
    if notify_url:
        log.info(f"BandcampSync will notify: {notify_url}")

    options = BandcampSyncOptions(
        cookies=cookies,
        dir_path=dir_path,
        media_format=media_format_env,
        temp_dir_root=temp_dir,
        ign_file_path=ign_file_path,
        ign_patterns=ign_patterns,
        notify_url=notify_url,
        until_date=until_date,
        dry_run=dry_run,
        concurrency=concurrency,
        max_retries=max_retries,
        retry_wait=retry_wait,
        skip_item_index=skip_item_index,
        sync_ignore_file=sync_ignore_file,
        skip_hidden=skip_hidden,
    )

    log.info(f"BandcampSync v{version} starting")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as e:
        raise ValueError(f"Not a valid timezone name: {tz_name}") from e
    try:
        run_daily_at = int(run_daily_at_env)
    except TypeError as e:
        raise ValueError(f"Invalid RUN_DAILY_AT, got: {run_daily_at_env}") from e
    if not 0 <= run_daily_at <= 23:
        raise ValueError(f"Invalid RUN_DAILY_AT, must be between 0 and 23, got: {run_daily_at}")
    try:
        exit_after_run = bool(int(exit_after_run_env))
    except (ValueError, TypeError):
        exit_after_run = False

    wake_event = threading.Event()
    state = SyncState()
    catch_shutdown = CatchShutdownSignal(wake_event)

    if not exit_after_run:
        start_http_server(http_port, state, log_tail, wake_event)
        log.info(f"Trigger UI listening on :{http_port} (POST /sync, GET /status)")

    log.info(f"Time now in {tz.key}: {datetime.now(tz).replace(microsecond=0)}")
    log.info("Running an initial one-off synchronisation immediately")

    try:
        run_scheduled_sync(
            options,
            run_daily_at,
            tz,
            exit_after_run,
            wake_event,
            state,
            should_shutdown=lambda: catch_shutdown.shutdown,
        )
    except KeyboardInterrupt:
        log.exception("Caught keyboard interrupt, stopping")
    log.info("Done")


if __name__ == "__main__":
    main()
