"""Logs a summary of everything that went wrong during a sync run."""

import logging

logger = logging.getLogger("sync")


def log_sync_error_summary(errors: list[str]) -> None:
    if not errors:
        return
    logger.warning(f"Sync completed with {len(errors)} error(s):")
    for error in errors:
        logger.warning(f"  - {error}")
