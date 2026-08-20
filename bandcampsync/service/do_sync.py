"""Entry point used by both the CLI (bin/bandcampsync) and the service loop."""

from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.service.sync_collection import sync_collection


def do_sync(options: BandcampSyncOptions) -> bool:
    sync_collection(options)
    return True
