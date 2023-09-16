#!/usr/bin/env python


import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from bandcampsync.logger import get_logger
from bandcampsync.bandcamp import Bandcamp
from bandcampsync.media import LocalMedia
from bandcampsync.download import Downloader


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
        band_name = purchase['band_name']
        title = purchase['item_title']
        if lm.is_locally_downloaded(item_id):
            log.info(f'Already locally downloaded, skipping: {item_id}')
            continue
        else:
            log.info(f'New media item, downloading: {item_id} ')
            download_url = bc.load_download_url(purchase)
            if not download_url:
                continue
            local_path = lm.get_path_for_purchase(purchase)
            with NamedTemporaryFile(mode='w+b', delete=True, suffix='.zip') as f:
                log.info(f'Downloading item {band_name} / {title} (id:{item_id}) '
                         f'from {download_url} to {f.name}')
                dl = Downloader(download_url)
                dl.stream(f)
                f.seek(0)
                with TemporaryDirectory() as tempdir:
                    log.info(f'Decompressing downloaded zip {f.name} to {tempdir}')
                    dl.decompress_download(f.name, tempdir)
                    temppath = Path(tempdir)
                    for filepath in temppath.iterdir():
                        if not local_path.is_dir():
                            local_path.mkdir(parents=True)
                        filedest = local_path / filepath.name
                        log.info(f'Moving extracted file: "{filepath}" to "{filedest}"')
                        shutil.move(filepath, filedest)
                log.info(f'Writing bandcamp item id to: {local_path}')
                lm.write_bandcamp_id(item_id, local_path)
    log.info(f'Refreshing cookies')
    with open(cookies_file, 'wt') as f:
        f.write(bc.cookies_str)
    log.info(f'Done')
