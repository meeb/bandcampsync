from enum import Enum, auto


class PlacementOutcome(Enum):
    PLACED = auto()
    RETRY_ATTEMPT = auto()
    UNRECOGNIZED_CONTENT = auto()
