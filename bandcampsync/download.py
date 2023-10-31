import math
import shutil
from zipfile import ZipFile
import requests
from .config import USER_AGENT
from .logger import get_logger


log = get_logger('download')


def mask_sig(url):
    if '&sig=' not in url:
        return url
    url_parts = url.split('&')
    for i, url_part in enumerate(url_parts):
        if url_part[:4] == 'sig=':
            url_parts[i] = 'sig=[masked]'
        elif url_part[:6] == 'token=':
            url_parts[i] = 'token=[masked]'
    return '&'.join(url_parts)


class DownloadBadStatusCode(ValueError):
    pass


class DownloadInvalidContentType(ValueError):
    pass


def download_file(url, target, mode='wb', chunk_size=8192, logevery=10, disallow_content_type='text/html'):
    """
        Attempts to stream a download to an open target file handle in chunks. If the
        request returns a disallowed content type then return a failed state with the
        response content.
    """
    text = True if 't' in mode else False
    data_streamed = 0
    last_log = 0
    headers = {'User-Agent': USER_AGENT}
    with requests.get(url, stream=True, headers=headers) as r:
        #r.raise_for_status()
        if r.status_code != 200:
            raise DownloadBadStatusCode(f'Got non-200 status code: {r.status_code}')
        try:
            content_type = r.headers.get('Content-Type', '')
        except (ValueError, KeyError):
            content_type = ''
        content_type_parts = content_type.split(';')
        major_content_type = content_type_parts[0].strip()
        if major_content_type == disallow_content_type:
            raise DownloadInvalidContentType(f'Invalid content type: {major_content_type}')
        try:
            content_length = int(r.headers.get('Content-Length', '0'))
        except (ValueError, KeyError):
            content_length = 0
        for chunk in r.iter_content(chunk_size=chunk_size):
            data_streamed += len(chunk)
            if text:
                chunk = chunk.decode()
            target.write(chunk)
            if content_length > 0 and logevery > 0:
                percent_complete = math.floor((data_streamed / content_length) * 100)
                if percent_complete % logevery == 0 and percent_complete > last_log:
                    log.info(f'Downloading {mask_sig(url)}: {percent_complete}%')
                    last_log = percent_complete
    return True


def is_zip_file(file_path):
    try:
        with ZipFile(file_path) as z:
            z.infolist()
        return True
    except Exception as e:
        return False


def unzip_file(decompress_from, decompress_to):
    with ZipFile(decompress_from) as z:
        z.extractall(decompress_to)
    return True


def move_file(src, dst):
    return shutil.move(src, dst)


def copy_file(src, dst):
    return shutil.copyfile(src, dst)
