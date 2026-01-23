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
    max_retries=3,
    retry_wait=5,
    skip_item_index=False,
    sync_ignore_file=False,
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
        max_retries,
        retry_wait,
        skip_item_index,
        sync_ignore_file,
    )

    return True
