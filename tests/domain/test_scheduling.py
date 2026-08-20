"""Tests for bandcampsync.domain.scheduling."""

from datetime import datetime, timezone

from bandcampsync.domain.scheduling import LogTail, SyncState, compute_next_run


def test_compute_next_run_lands_on_target_hour_tomorrow() -> None:
    now = datetime(2026, 8, 20, 14, 30, tzinfo=timezone.utc)
    next_run, sleep_seconds = compute_next_run(now, run_daily_at=3, random_delay=0)
    assert next_run == datetime(2026, 8, 21, 3, 0, tzinfo=timezone.utc)
    assert sleep_seconds == int((next_run - now).total_seconds())


def test_compute_next_run_adds_random_delay() -> None:
    now = datetime(2026, 8, 20, 14, 30, tzinfo=timezone.utc)
    _, sleep_seconds = compute_next_run(now, run_daily_at=3, random_delay=0)
    _, sleep_seconds_with_delay = compute_next_run(now, run_daily_at=3, random_delay=120)
    assert sleep_seconds_with_delay == sleep_seconds + 120


def test_compute_next_run_when_now_is_past_target_hour() -> None:
    # Run-hour already passed today - should still land tomorrow, not today.
    now = datetime(2026, 8, 20, 23, 59, tzinfo=timezone.utc)
    next_run, _ = compute_next_run(now, run_daily_at=0, random_delay=0)
    assert next_run == datetime(2026, 8, 21, 0, 0, tzinfo=timezone.utc)


def test_sync_state_starts_idle() -> None:
    state = SyncState()
    snapshot = state.to_dict()
    assert snapshot["status"] == "idle"
    assert snapshot["last_run_started"] is None
    assert snapshot["last_result"] is None


def test_sync_state_tracks_a_run() -> None:
    state = SyncState()
    state.mark_running()
    assert state.to_dict()["status"] == "running"

    state.mark_finished("ok", next_scheduled="2026-08-21T03:00:00+00:00")
    snapshot = state.to_dict()
    assert snapshot["status"] == "idle"
    assert snapshot["last_result"] == "ok"
    assert snapshot["next_scheduled"] == "2026-08-21T03:00:00+00:00"
    assert snapshot["last_run_finished"] is not None


def test_sync_state_keeps_next_scheduled_when_not_given() -> None:
    state = SyncState()
    state.mark_finished("ok", next_scheduled="2026-08-21T03:00:00+00:00")
    state.mark_running()
    state.mark_finished("ok")
    assert state.to_dict()["next_scheduled"] == "2026-08-21T03:00:00+00:00"


def test_log_tail_keeps_only_the_most_recent_lines() -> None:
    log_tail = LogTail(capacity=3)
    logger_name = "bandcampsync.test.log_tail"
    import logging

    logger = logging.getLogger(logger_name)
    logger.addHandler(log_tail)
    logger.setLevel(logging.INFO)
    for i in range(5):
        logger.info(f"line {i}")

    tail = log_tail.tail()
    assert len(tail) == 3
    assert "line 4" in tail[-1]
    assert "line 2" in tail[0]
