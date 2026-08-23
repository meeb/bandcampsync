from dataclasses import dataclass, field


@dataclass
class SyncOutcome:
    new_items_downloaded: bool
    errors: list[str] = field(default_factory=list)

    @property
    def had_errors(self) -> bool:
        return bool(self.errors)
