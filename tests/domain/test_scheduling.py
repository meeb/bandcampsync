"""Tests for bandcampsync.domain.scheduling."""

from datetime import datetime, timezone

from bandcampsync.domain.scheduling import compute_next_run


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
