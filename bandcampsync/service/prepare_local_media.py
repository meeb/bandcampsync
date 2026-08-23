"""Decides whether this run can resume from the collection checkpoint, and
builds the local media index accordingly.
"""

import logging

from bandcampsync.domain.collection import load_checkpoint
from bandcampsync.domain.ignore_entry import IgnoreFileWriter, IgnoreRules
from bandcampsync.domain.media import LocalMedia
from bandcampsync.domain.options import BandcampSyncOptions

log = logging.getLogger("sync")


def prepare_local_media(
    options: BandcampSyncOptions, ignore_rules: IgnoreRules, ignore_file_writer: IgnoreFileWriter
) -> tuple[LocalMedia, str | None, bool]:
    """Returns (local_media, checkpoint_token, use_collection_checkpoint).

    use_collection_checkpoint is False whenever options.until_date is set -
    an ad-hoc backfill run shouldn't advance (or trust) the regular
    collection checkpoint. When a checkpoint token is available, the local
    media directory is not walked up front, since load_purchases will stop
    as soon as it reaches the checkpointed item anyway.
    """
    use_collection_checkpoint = not options.until_date
    checkpoint_token = load_checkpoint(options.dir_path) if use_collection_checkpoint else None
    index_local_media = not checkpoint_token
    if not index_local_media:
        log.info("Collection checkpoint loaded; skipping initial local media index")
    local_media = LocalMedia(
        media_dir=options.dir_path,
        ignore_rules=ignore_rules,
        ignore_file_writer=ignore_file_writer,
        skip_item_index=options.skip_item_index,
        sync_ignore_file=options.sync_ignore_file,
        index_on_init=index_local_media,
    )
    return local_media, checkpoint_token, use_collection_checkpoint
