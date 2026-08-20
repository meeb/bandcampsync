"""Runs sync on a daily schedule, interruptible on demand via a wake event.

The upstream loop used time.sleep() for up to a day at a stretch, which is
cheap (a blocking syscall, not a busy-wait) but uninterruptible except by
killing the process. Waiting on a threading.Event instead costs nothing extra
while idle, but lets the HTTP trigger interface wake it early for an
on-demand sync without disturbing the next scheduled run.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from random import randrange
from zoneinfo import ZoneInfo

from bandcampsync.domain import SyncState, compute_next_run
from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.service.do_sync import do_sync

# Plain logging.getLogger, not get_logger(): interface/service/entrypoint.py
# already calls get_logger("service") once to attach its console handler.
# Doing that again here would attach a second handler and double every line.
log = logging.getLogger("service")


def run_scheduled_sync(
    options: BandcampSyncOptions,
    run_daily_at: int,
    tz: ZoneInfo,
    exit_after_run: bool,
    wake_event: threading.Event,
    state: SyncState,
    should_shutdown: Callable[[], bool],
) -> None:
    """Runs do_sync on the daily schedule until should_shutdown() is true."""
    run_scheduled_sync_with(
        options,
        run_daily_at,
        tz,
        exit_after_run,
        wake_event,
        state,
        should_shutdown,
    )


def run_scheduled_sync_with(
    options: BandcampSyncOptions,
    run_daily_at: int,
    tz: ZoneInfo,
    exit_after_run: bool,
    wake_event: threading.Event,
    state: SyncState,
    should_shutdown: Callable[[], bool],
    sync: Callable[[BandcampSyncOptions], bool] = do_sync,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    random_delay: Callable[[], int] = lambda: randrange(0, 3600),  # noqa: S311 - scheduling jitter, not crypto
    wait: Callable[[threading.Event, int], bool] = lambda event, timeout: event.wait(
        timeout=timeout
    ),
    logger_: logging.Logger = log,
) -> None:
    """run_scheduled_sync with injectable dependencies for testing.

    Args:
        sync:        Performs one sync run. Swap in a fake to avoid hitting bandcamp.com.
        now:         Returns the current time (timezone-aware). Swap in a fixed clock.
        random_delay: Returns the jitter seconds added to each schedule. Swap in a fixed value.
        wait:        Blocks until wake_event is set or timeout elapses. Swap in a fake to
                     avoid real wall-clock waits in tests.
        logger_:     Logger to use; defaults to this module's logger.
    """
    while not should_shutdown():
        logger_.info("Starting synchronisation")
        state.mark_running()
        try:
            sync(options)
            result = "ok"
        except Exception as e:
            logger_.exception("Synchronisation failed")
            result = f"error: {e}"

        current_time = now().astimezone(tz).replace(microsecond=0)
        next_run, sleep_seconds = compute_next_run(current_time, run_daily_at, random_delay())
        state.mark_finished(result, next_scheduled=next_run.isoformat())

        if exit_after_run:
            logger_.info("Exiting after run")
            break

        logger_.info(f"Scheduling next run for {next_run}")
        logger_.info(
            f"Waiting up to {sleep_seconds}s, or until a sync is requested via the trigger UI"
        )
        wait(wake_event, sleep_seconds)
        woke_early = wake_event.is_set() and not should_shutdown()
        wake_event.clear()
        if woke_early:
            logger_.info("Woken early by an on-demand sync request")
