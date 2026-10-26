from .options import BandcampSyncOptions
from .config import VERSION as version
from .sync import Syncer


__all__ = ["version", "do_sync", "Syncer", "BandcampSyncOptions"]


def do_sync(options: BandcampSyncOptions):
    Syncer(options, auto_run=True)
    return True
