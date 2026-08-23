"""The shape of a local media directory snapshot: pure data, no business
methods. Immutable - it's a point-in-time result of walking the directory
(see index.py); LocalMedia keeps its own live, mutable working copy seeded
from one of these (walking a filesystem tree concurrently-safely as an
immutable value getting rebuilt on every discovery isn't worth it here -
see local_media_entry/checks.py for why the live cache stays a plain
mutable dict/set instead).
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class MediaIndex(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_item_id: dict[int, Path] = {}
    item_names: frozenset[tuple[str, str]] = frozenset()
