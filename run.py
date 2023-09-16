#!/usr/bin/env python


import os
from pathlib import Path
from bandcampsync.logger import get_logger
from bandcampsync.bandcamp import Bandcamp
from bandcampsync.media import LocalMedia


log = get_logger('run')

DIR = '/home/meeb/bandcamp'


if __name__ == '__main__':
    log.info(f'Starting')
    cookies_file_str = os.getenv('BANDCAMP_COOKIES_FILE', 'cookies.txt')
    if not cookies_file_str:
        raise ValueError(f'env var BANDCAMP_COOKIES_FILE must be set')
    cookies_file = Path(cookies_file_str).resolve()
    if not cookies_file.is_file():
        raise ValueError(f'Cookies file "{cookies_file}" does not exist')
    with open(cookies_file, 'rt') as f:
        cookies = f.read().strip()
    log.info(f'Loaded cookies from "{cookies_file}"')
    lm = LocalMedia(media_dir=Path(DIR))
    bc = Bandcamp(cookies=cookies)
    bc.verify_authentication()
    bc.load_purchases()
    for purchase in bc.purchases:
        item_id = purchase['item_id']
        if lm.is_locally_downloaded(item_id):
            log.info(f'Already locally downloaded, skipping: {item_id}')
            continue
        else:
            log.info(f'New media item, downloading: {item_id}')
            download_url = bc.load_download_url(purchase)
            if not download_url:
                continue
            log.info(f'Downloading {item_id} from {download_url}')
        break
    log.info(f'Done')
