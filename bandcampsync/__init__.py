import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from .config import VERSION as version
from .logger import get_logger
from .bandcamp import Bandcamp, BandcampError
from .media import LocalMedia
from .download import (download_file, unzip_file, move_file, copy_file,
                       mask_sig, is_zip_file, DownloadInvalidContentType,
                       DownloadBadStatusCode)


log = logger.get_logger('sync')


def do_sync(cookies_path, cookies, dir_path, media_format, temp_dir_root, ign_patterns):
    local_media = LocalMedia(media_dir=dir_path)
    bandcamp = Bandcamp(cookies=cookies)
    bandcamp.verify_authentication()
    bandcamp.load_purchases()
    for item in bandcamp.purchases:

        # Check if any ignore pattern matches the band name
        ignored = False
        for pattern in ign_patterns.split():
            if pattern.lower() in item.band_name.lower():
                log.warning(f'Skipping item due to ignore pattern: "{pattern}" found in "{item.band_name}"')
                ignored = True
                break
        if ignored:
            continue

        local_path = local_media.get_path_for_purchase(item)
        if item.is_preorder == True:
            log.info(f'Item is a preorder, skipping: "{item.band_name} / {item.item_title}" '
                     f'(id:{item.item_id})')
            continue
        elif local_media.is_locally_downloaded(item, local_path):
            log.info(f'Already locally downloaded, skipping: "{item.band_name} / {item.item_title}" '
                     f'(id:{item.item_id})')
            continue
        else:
            log.info(f'New media item, will download: "{item.band_name} / {item.item_title}" '
                     f'(id:{item.item_id}) in "{media_format}"')
            try:
                local_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                log.error('Failed to create directory: {local_path} ({e}), skipping purchase...')
                continue
            try:
                initial_download_url = bandcamp.get_download_file_url(item, encoding=media_format)
            except BandcampError as e:
                log.error(f'Failed to locate download URL for media item "{item.band_name} / {item.item_title}" '
                          f'(id:{item.item_id}), unable to download release ({e}), skipping')
                continue
            download_file_url = bandcamp.check_download_stat(item, initial_download_url)
            with NamedTemporaryFile(mode='w+b', delete=True, dir=temp_dir_root) as temp_file:
                log.info(f'Downloading item "{item.band_name} / {item.item_title}" (id:{item.item_id}) '
                         f'from {mask_sig(download_file_url)} to {temp_file.name}')
                try:
                    download_file(download_file_url, temp_file)
                except DownloadBadStatusCode as e:
                    log.error(f'Download attempt returned an unexpected status code ({e}), skipping')
                    continue
                except DownloadInvalidContentType as e:
                    log.error(f'Download attempt returned an unexpected content type ({e}), skipping')
                    continue
                temp_file.seek(0)
                temp_file_path = Path(temp_file.name)
                if is_zip_file(temp_file_path):
                    with TemporaryDirectory(dir=temp_dir_root) as temp_dir:
                        log.info(f'Decompressing downloaded zip "{temp_file.name}" to "{temp_dir}"')
                        unzip_file(temp_file.name, temp_dir)
                        temp_path = Path(temp_dir)
                        for file_path in temp_path.iterdir():
                            file_dest = local_media.get_path_for_file(local_path, file_path.name)
                            log.info(f'Moving extracted file: "{file_path}" to "{file_dest}"')
                            try:
                                move_file(file_path, file_dest)
                            except Exception as e:
                                log.error(f'Failed to move {file_path} to {file_dest}: {e}')
                    local_media.write_bandcamp_id(item, local_path)
                elif item.item_type == 'track':
                    slug = item.url_hints.get('slug', item.item_title)
                    format_extension = local_media.clean_format(media_format)
                    file_dest = local_media.get_path_for_file(local_path, f'{slug}.{format_extension}')
                    log.info(f'Copying single track: "{temp_file_path}" to "{file_dest}"')
                    try:
                        copy_file(temp_file_path, file_dest)
                    except Exception as e:
                        log.error(f'Failed to copy {file_path} to {file_dest}: {e}')
                    local_media.write_bandcamp_id(item, local_path)
                else:
                    log.error(f'Downloaded file for "{item.band_name} / {item.item_title}" (id:{item.item_id}) '
                              f'at "{temp_file_path}" is not a zip archive or a single track, skipping')
    return True
