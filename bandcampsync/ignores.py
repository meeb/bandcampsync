import os
import shutil
from .logger import get_logger


TEMPLATE_IGNORES_FILE = '/ignores.template.txt'
log = get_logger('ignores')


class Ignores:
    """Manages configuration for items that shouldn't be downloaded."""

    def __init__(self, ign_file_path, ign_patterns):
        self.ign_file_path = ign_file_path
        if self.ign_file_path:
            log.info(f'Ignore file: {self.ign_file_path}')
        # List of substring patterns for band_name
        self.band_patterns = [pattern.lower() for pattern in ign_patterns.split()]
        if self.band_patterns:
            log.info(f'Using {len(self.band_patterns)} ignore patterns')

        self.ids = set()
        self.parse_ignores()

    def parse_ignores(self):
        if not self.ign_file_path:
            log.info(f'No ignore file specified')
            return

        # If a file path is specified, but there is no such file (e.g. first
        # run on Docker) we create it. We can't do it in the Dockerfile
        # because it must be created in the mounted volume.
        if not os.path.exists(self.ign_file_path):
            log.warning(f'Ignore file {self.ign_file_path} not found. Creating a blank one')
            with open(self.ign_file_path, 'wt') as f:
                shutil.copyfile(TEMPLATE_IGNORES_FILE, self.ign_file_path)

        with open(self.ign_file_path, 'rt') as f:
            try:
                lines = f.readlines()
            except Exception as e:
                raise ValueError(f'Failed to read ignore file {self.ign_file_path}: {e}')
        lines = [line.split('#')[0].strip() for line in lines] # Strip comments
        lines = [line for line in lines if line] # Remove empty lines
        for line in lines:
            try:
                self.ids.add(int(line))
            except Exception as e:
                raise ValueError(f'Failed to cast item ID from {self.ign_file_path} "{line}" as an int: {e}')

    def is_ignored(self, item):
        # Check if the id is ignored
        if item.item_id in self.ids:
            log.warning(f'Skipping item {item.band_name} / {item.item_title} due to its id {item.item_id} being present in the ignore file')
            return True

        # Check if any ignore pattern matches the band name
        for pattern in self.band_patterns:
            if pattern in item.band_name.lower():
                log.warning(f'Skipping item due to ignore pattern: "{pattern}" found in "{item.band_name}"')
                return True
        return False

