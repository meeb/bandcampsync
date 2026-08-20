from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class BandcampSyncOptions:
    cookies: str
    dir_path: Path
    media_format: str = "flac"
    temp_dir_root: Path | None = None
    ign_file_path: Path | None = None
    ign_patterns: str = ""
    notify_url: str | None = None
    until_date: date | None = None
    dry_run: bool = False
    concurrency: int = 1
    max_retries: int = 3
    retry_wait: int = 5
    skip_item_index: bool = False
    sync_ignore_file: bool = False
    skip_hidden: bool = False
