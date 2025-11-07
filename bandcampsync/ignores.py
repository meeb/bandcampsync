from .logger import get_logger


log = get_logger('ignores')


class Ignores:
    """Manages configuration for items that shouldn't be downloaded."""

    def __init__(self, ign_patterns):
        # List of substring patterns for band_name
        self.band_patterns = [pattern.lower() for pattern in ign_patterns.split()]
        if self.band_patterns:
            log.info(f'Using {len(self.band_patterns)} ignore patterns')

    def is_ignored(self, item):
        # Check if any ignore pattern matches the band name
        for pattern in self.band_patterns:
            if pattern in item.band_name.lower():
                log.warning(f'Skipping item due to ignore pattern: "{pattern}" found in "{item.band_name}"')
                return True
        return False

