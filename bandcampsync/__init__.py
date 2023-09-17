from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from .config import VERSION as version
from .logger import get_logger
from .bandcamp import Bandcamp
from .media import LocalMedia
from .download import download_file, unzip_file, move_file, mask_sig, is_zip_file


log = logger.get_logger('sync')


def do_sync(cookies, dir_path, media_format):
    local_media = LocalMedia(media_dir=dir_path)
    bandcamp = Bandcamp(cookies=cookies)
    bandcamp.verify_authentication()
    bandcamp.load_purchases()
    for purchase in bandcamp.purchases:
        item_id = purchase['item_id']
        band_name = purchase['band_name']
        title = purchase['item_title']
        if local_media.is_locally_downloaded(item_id):
            log.info(f'Already locally downloaded, skipping: {band_name} / {title} (id:{item_id})')
            continue
        else:
            log.info(f'New media item, downloading: {band_name} / {title} (id:{item_id}) in "{media_format}"')
            download_url = bandcamp.load_download_url(purchase, encoding=media_format)
            if not download_url:
                log.error(f'Failed to find download URL for: {item_id} with format: {media_format}')
                continue
            local_path = local_media.get_path_for_purchase(purchase)
            with NamedTemporaryFile(mode='w+b', delete=True, suffix='.zip') as temp_file:
                log.info(f'Downloading item {band_name} / {title} (id:{item_id}) '
                         f'from {mask_sig(download_url)} to {temp_file.name}')
                download_file(download_url, temp_file)
                temp_file.seek(0)
                if is_zip_file(temp_file):
                    with TemporaryDirectory() as temp_dir:
                        log.info(f'Decompressing downloaded zip {temp_file.name} to {temp_dir}')

                        unzip_file(temp_file.name, temp_dir)
                        temp_path = Path(temp_dir)
                        for file_path in temp_path.iterdir():
                            if not local_path.is_dir():
                                local_path.mkdir(parents=True)
                            file_dest = local_path / file_path.name
                            log.info(f'Moving extracted file: "{file_path}" to "{file_dest}"')
                            move_file(file_path, file_dest)
                    local_media.write_bandcamp_id(item_id, local_path)
                else:
                    log.info(f'Downloaded file is not a zip archive, assuming it is a single track: {temp_file.name}')
                    temp_path = Path(temp_file)
                    file_dest = local_path / f'{title}.{media_format}'
                    log.info(f'Moving single file: "{temp_path}" to "{file_dest}"')
    bandcamp.refresh_cookes(cookies_path)
    return True
