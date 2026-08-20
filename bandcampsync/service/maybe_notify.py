"""Fires the configured notify URL if this run downloaded anything new."""

import logging

from bandcampsync.domain.notify import NotifyURL

logger = logging.getLogger("sync")


def maybe_notify(dry_run: bool, new_items_downloaded: bool, notify_url: str | None) -> None:
    if dry_run:
        logger.info("Dry run enabled: skipping notify")
        return
    if new_items_downloaded and notify_url is not None:
        NotifyURL(notify_url).notify()
