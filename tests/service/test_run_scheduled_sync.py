"""Tests for bandcampsync.service.run_scheduled_sync."""

import threading
from datetime import datetime, timezone

from bandcampsync.domain import SyncState
from bandcampsync.service.run_scheduled_sync import run_scheduled_sync_with


def _fixed_now() -> datetime:
    return datetime(2026, 8, 20, 14, 30, tzinfo=timezone.utc)


def _never_waits(event: threading.Event, timeout: int) -> bool:
    return event.wait(timeout=0)


def test_exit_after_run_syncs_once_and_stops() -> None:
    calls = []
    wake_event = threading.Event()
    state = SyncState()

    run_scheduled_sync_with(
        options=object(),
        run_daily_at=3,
        tz=timezone.utc,
        exit_after_run=True,
        wake_event=wake_event,
        state=state,
        should_shutdown=lambda: False,
        sync=lambda opts: calls.append(opts),
        now=_fixed_now,
        random_delay=lambda: 0,
        wait=_never_waits,
    )

    assert len(calls) == 1
    snapshot = state.to_dict()
    assert snapshot["status"] == "idle"
    assert snapshot["last_result"] == "ok"
    assert snapshot["next_scheduled"] == "2026-08-21T03:00:00+00:00"


def test_sync_failure_is_recorded_and_does_not_crash_the_loop() -> None:
    wake_event = threading.Event()
    state = SyncState()

    def failing_sync(opts: object) -> None:
        raise RuntimeError("bandcamp.com is down")

    run_scheduled_sync_with(
        options=object(),
        run_daily_at=3,
        tz=timezone.utc,
        exit_after_run=True,
        wake_event=wake_event,
        state=state,
        should_shutdown=lambda: False,
        sync=failing_sync,
        now=_fixed_now,
        random_delay=lambda: 0,
        wait=_never_waits,
    )

    assert state.to_dict()["last_result"] == "error: bandcamp.com is down"


def test_stops_when_should_shutdown_becomes_true() -> None:
    call_count = 0

    def sync(opts: object) -> None:
        nonlocal call_count
        call_count += 1

    shutdown_after = 2
    iterations = 0

    def should_shutdown() -> bool:
        nonlocal iterations
        result = iterations >= shutdown_after
        iterations += 1
        return result

    run_scheduled_sync_with(
        options=object(),
        run_daily_at=3,
        tz=timezone.utc,
        exit_after_run=False,
        wake_event=threading.Event(),
        state=SyncState(),
        should_shutdown=should_shutdown,
        sync=sync,
        now=_fixed_now,
        random_delay=lambda: 0,
        wait=_never_waits,
    )

    assert call_count == shutdown_after


def test_wake_event_triggers_immediate_next_iteration() -> None:
    wake_event = threading.Event()
    wake_event.set()  # simulate an on-demand /sync request arriving before the wait
    call_count = 0

    def sync(opts: object) -> None:
        nonlocal call_count
        call_count += 1

    def should_shutdown() -> bool:
        return call_count >= 2

    def wait_and_report(event: threading.Event, timeout: int) -> bool:
        return event.wait(timeout=0)

    run_scheduled_sync_with(
        options=object(),
        run_daily_at=3,
        tz=timezone.utc,
        exit_after_run=False,
        wake_event=wake_event,
        state=SyncState(),
        should_shutdown=should_shutdown,
        sync=sync,
        now=_fixed_now,
        random_delay=lambda: 0,
        wait=wait_and_report,
    )

    assert call_count == 2
    assert not wake_event.is_set()  # cleared after being consumed
