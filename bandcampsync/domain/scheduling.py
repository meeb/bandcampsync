"""Pure scheduling math for the sync service loop.

Pulled out as a pure function (no clock access, no randomness of its own)
specifically so the daily-schedule math is testable without waiting on a
real day boundary or mocking datetime.now.
"""

from datetime import datetime, timedelta


def compute_next_run(now: datetime, run_daily_at: int, random_delay: int) -> tuple[datetime, int]:
    """Compute the next scheduled run time and how many seconds until then.

    Args:
        now: Current time, timezone-aware, in the target timezone.
        run_daily_at: Hour of day (0-23) the daily run should land on.
        random_delay: Extra seconds of jitter to add on top of the hour boundary.

    Returns:
        (next_run, sleep_seconds) - next_run is tomorrow at run_daily_at:00:00,
        sleep_seconds is the whole-second gap between now and next_run plus jitter.
    """
    next_run = now.replace(hour=run_daily_at, minute=0, second=0, microsecond=0)
    next_run += timedelta(days=1)
    sleep_seconds = int((next_run - now).total_seconds() + random_delay)
    return next_run, sleep_seconds
