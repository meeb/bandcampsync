from dataclasses import dataclass
from pathlib import Path

from bandcampsync.domain.bandcamp import BandcampSession
from bandcampsync.domain.ignores import Ignores
from bandcampsync.domain.media import LocalMedia


@dataclass(frozen=True)
class PurchaseDownloadContext:
    """Dependencies and settings shared across every purchase downloaded in one run."""

    bandcamp: BandcampSession
    local_media: LocalMedia
    ignores: Ignores
    media_format: str
    temp_dir_root: Path | None
    max_retries: int
    retry_wait: int
    dry_run: bool
    skip_hidden: bool
    ign_file_path: Path | None


@dataclass(frozen=True)
class PurchaseDownloadResult:
    downloaded: bool
    # True if this purchase is locally downloaded only via the legacy
    # per-directory bandcamp_item_id.txt file, not the shared ignore file.
    show_id_file_warning: bool
