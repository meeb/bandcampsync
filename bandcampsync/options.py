from dataclasses import dataclass
from pathlib import Path
from datetime import date
from typing import Optional
from .notify import NotifyURL


@dataclass
class BandcampSyncOptions:
    cookies: str
    dir_path: Path
    media_format: str = "flac"
    temp_dir_root: Optional[Path] = None
    ign_file_path: Optional[Path] = None
    ign_patterns: str = ""
    notify_url: Optional[str] = None
    until_date: Optional[date] = None
    dry_run: bool = False
    concurrency: int = 1
    max_retries: int = 3
    retry_wait: int = 5
    skip_item_index: bool = False
    sync_ignore_file: bool = False
    skip_hidden: bool = False
    impersonate: Optional[str] = None

    def __post_init__(self):
        # Bad notify settings fail now, rather than after a sync has downloaded something
        self.notify_url = (self.notify_url or "").strip() or None
        if self.notify_url and not NotifyURL(self.notify_url).valid:
            raise ValueError("Invalid notify URL, see the error logged above")
