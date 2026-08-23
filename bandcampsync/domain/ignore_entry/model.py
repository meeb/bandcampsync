"""The shape of the ignore configuration: pure data, no business methods."""

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict


class IgnoreRules(BaseModel):
    """What should be skipped: explicit item ids and band-name substring
    patterns. Immutable - nothing here is ever mutated in place, unlike the
    on-disk file's layout (see IgnoreFileLayout).
    """

    model_config = ConfigDict(frozen=True)

    ids: frozenset[int] = frozenset()
    band_patterns: tuple[str, ...] = ()


@dataclass
class IgnoreFileLayout:
    """Parse-result bookkeeping needed to rewrite the ignore file while
    preserving the user's original comments/formatting - not rule data
    (that's IgnoreRules), just file-format state.
    """

    lines: list[str] = field(default_factory=list)
    # The line number at which to insert the next downloaded item id.
    insert_index: int = -1
