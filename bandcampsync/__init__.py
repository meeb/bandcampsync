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
    until_date=None,
    dry_run=False,
    concurrency=1,
    max_retries=3,
    retry_wait=5,
    skip_item_index=False,
    sync_ignore_file=False,
    skip_hidden=False,
):
    Syncer(
        cookies,
        dir_path,
        media_format,
        temp_dir_root,
        ign_file_path,
        ign_patterns,
        notify_url,
        until_date,
        dry_run,
        concurrency,
        max_retries,
        retry_wait,
        skip_item_index,
        sync_ignore_file,
        skip_hidden,
    )

    return True
