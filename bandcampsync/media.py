from .logger import get_logger


log = get_logger('media')


class LocalMedia:
    """
        A local media directory. This stores media in the following format:

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
        log.info(f'Local media directory: {self.media_dir}')
        self.index()

    def index(self):
        for child1 in self.media_dir.iterdir():
            if child1.is_dir():
                for child2 in child1.iterdir():
                    if child2.is_dir():
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
            raise ValueError(f'Failed to cast item ID "{item_id}" as an int: {e}') from e

    def is_locally_downloaded(self, item_id):
        return item_id in self.media
