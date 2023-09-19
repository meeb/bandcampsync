from unicodedata import normalize
from .logger import get_logger


log = get_logger('media')


class LocalMedia:
    """
        A local media directory indexer. This stores media in the following format:

            /media_dir/
            /media_dir/Artist Name
            /media_dir/Artist Name/Album Name
            /media_dir/Artist Name/Album Name/bandcamp_item_id.txt
            /media_dir/Artist Name/Album Name/track1.flac
            /media_dir/Artist Name/Album Name/track2.flac
    """

    ITEM_INDEX_FILENAME = 'bandcamp_item_id.txt'

    def __init__(self, media_dir):
        self.media_dir = media_dir
        self.media = {}
        self.dirs = set()
        log.info(f'Local media directory: {self.media_dir}')
        self.index()

    def _clean_path(self, path_str):
        path_str = str(path_str)
        disallowed_punctuation = '"#%\'*/?\\`'
        normalized_path = normalize('NFKD', path_str)
        outstr = ''
        for c in normalized_path:
            if c not in disallowed_punctuation:
                outstr += c
        return outstr

    def index(self):
        for child1 in self.media_dir.iterdir():
            if child1.is_dir():
                for child2 in child1.iterdir():
                    if child2.is_dir():
                        self.dirs.add(child2)
                        for child3 in child2.iterdir():
                            if child3.name == self.ITEM_INDEX_FILENAME:
                                item_id = self.read_item_id(child3)
                                self.media[item_id] = child2
                                log.info(f'Detected locally downloaded media: {item_id} = {child2}')
        return True

    def read_item_id(self, filepath):
        with open(filepath, 'rt') as f:
            item_id = f.read().strip()
        try:
            return int(item_id)
        except Exception as e:
            raise ValueError(f'Failed to cast item ID from {filepath} "{item_id}" as an int: {e}') from e

    def is_locally_downloaded(self, item_id):
        return item_id in self.media

    def is_dir(self, path):
        return path in self.dirs

    def get_path_for_purchase(self, item):
        return self.media_dir / self._clean_path(item.band_name) / self._clean_path(item.item_title)

    def get_path_for_file(self, local_path, file_name):
        return local_path / self._clean_path(file_name)

    def write_bandcamp_id(self, item, dirpath):
        outfile = dirpath / self.ITEM_INDEX_FILENAME
        log.info(f'Writing bandcamp item id:{item.item_id} to: {outfile}')
        with open(outfile, 'wt') as f:
            f.write(f'{item.item_id}\n')
        return True
