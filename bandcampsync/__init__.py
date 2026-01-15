from .config import VERSION as version
from .sync import Syncer


__all__ = ["version", "do_sync", "Syncer"]


def do_sync(
    cookies,
    dir_path,
    media_format,
    temp_dir_root,
    ign_file_path,
    ign_patterns,
    notify_url,
    concurrency=1,
):
    Syncer(
        cookies,
        dir_path,
        media_format,
        temp_dir_root,
        ign_file_path,
        ign_patterns,
        notify_url,
        concurrency,
    )

    return True
