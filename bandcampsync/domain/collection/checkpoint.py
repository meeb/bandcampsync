"""Reads and writes the .bandcampsync-state.json checkpoint file, letting a
sync stop paginating purchases as soon as it reaches the last-seen item
instead of re-scanning the full collection every run.

Uses the shared "sync" logger via plain logging.getLogger rather than the
get_logger() wrapper - that wrapper attaches a new StreamHandler every time
it's called, and it's already called once (in service/sync_collection.py) to
configure this same named logger. Calling it again here would double every
log line.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.collection.purchase_selection import item_token
from bandcampsync.domain.utils import atomic_write_text

log = logging.getLogger("sync")

STATE_FILENAME = ".bandcampsync-state.json"
STATE_VERSION = 1


def state_file_path(media_dir: Path) -> Path:
    return media_dir / STATE_FILENAME


def load_checkpoint(media_dir: Path) -> str | None:
    state_file = state_file_path(media_dir)
    if not state_file.is_file():
        return None
    try:
        with state_file.open(encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError) as parse_error:
        log.warning(f'Failed to parse state file "{state_file}": {parse_error}')
        return None
    if not isinstance(state, dict):
        log.warning(f'Ignoring invalid state file "{state_file}": expected JSON object')
        return None
    token = state.get("last_seen_token")
    if not isinstance(token, str) or not token:
        return None
    log.info(f'Loaded collection checkpoint from "{state_file}"')
    return token


def resolve_checkpoint_candidate(
    purchases: list[BandcampItem], collection_items: list[BandcampItem]
) -> tuple[BandcampItem, str] | None:
    """Picks which item to checkpoint against: the newest collection item if
    any were seen this run, falling back to the newest purchase. Returns None
    if there's nothing to checkpoint, or the chosen item has no usable token.
    """
    candidates = collection_items or purchases
    if not candidates:
        return None
    newest_item = candidates[0]
    token = item_token(newest_item)
    if not token:
        return None
    return newest_item, token


def save_checkpoint(media_dir: Path, item: BandcampItem, token: str) -> None:
    state: dict[str, Any] = {
        "version": STATE_VERSION,
        "last_seen_token": token,
        "last_seen_item_id": item.item_id,
        "last_seen_purchased": item.purchased,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    state_file = state_file_path(media_dir)
    try:
        atomic_write_text(state_file, json.dumps(state, indent=2, sort_keys=True) + "\n")
        log.info(f'Updated collection checkpoint: "{state_file}"')
    except OSError:
        log.exception(f'Failed to write collection checkpoint "{state_file}"')
