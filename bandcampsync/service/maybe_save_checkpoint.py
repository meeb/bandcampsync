"""Decides whether this run should advance the collection checkpoint, and does so if so."""

import logging
from pathlib import Path

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.collection import resolve_checkpoint_candidate, save_checkpoint

logger = logging.getLogger("sync")


def maybe_save_checkpoint(
    media_dir: Path,
    use_collection_checkpoint: bool,
    dry_run: bool,
    had_errors: bool,
    purchases: list[BandcampItem],
    collection_items: list[BandcampItem],
) -> None:
    if not use_collection_checkpoint:
        return
    if dry_run:
        logger.info("Dry run enabled: not updating collection checkpoint")
        return
    if had_errors:
        logger.warning("Sync had errors; not advancing collection checkpoint")
        return
    candidate = resolve_checkpoint_candidate(purchases, collection_items)
    if candidate is None:
        return
    newest_item, newest_token = candidate
    save_checkpoint(media_dir, newest_item, newest_token)
