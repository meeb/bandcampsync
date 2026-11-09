import math
import os
import re
import shutil
import zlib
from contextlib import contextmanager
from pathlib import Path
from tempfile import mkstemp
from zipfile import BadZipFile, ZipFile
from bs4 import BeautifulSoup
from curl_cffi import requests
from .logger import get_logger
from .names import fit_name, unique_name


log = get_logger("download")


def mask_sig(url):
    return re.sub(r"([?&](?:sig|token)=)[^&]*", r"\1[masked]", url)


class DownloadBadStatusCode(ValueError):
    pass


class DownloadInvalidContentType(ValueError):
    pass


class DownloadExpired(ValueError):
    pass


class DownloadCorrupt(ValueError):
    pass


class DownloadEmpty(ValueError):
    pass


class DownloadUnexpectedLayout(ValueError):
    pass


def _is_expired_download_page(html):
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    reauth_error = soup.select_one("div.email-reauth-error")
    if not reauth_error:
        return False
    style = str(reauth_error.get("style")) or ""
    style = style.replace(" ", "").lower()
    return "display:none" not in style


def _fetch_html_body(url, impersonate):
    if not url:
        return ""
    try:
        resp = requests.get(url, stream=False, impersonate=impersonate)
    except requests.exceptions.RequestException as e:
        log.warning(f"Failed to fetch HTML body for: {mask_sig(url)} ({e})")
        return ""
    try:
        return resp.text or ""
    finally:
        resp.close()


def _read_html_body(response, impersonate):
    html_body = ""
    try:
        html_body = response.text or ""
    except requests.exceptions.RequestException as e:
        log.warning(f"Failed to read HTML body for: {mask_sig(response.url)} ({e})")
        pass
    if not html_body:
        try:
            html_body = response.content.decode("utf-8", errors="replace")
        except requests.exceptions.RequestException as e:
            log.warning(
                f"Failed to decode HTML body for: {mask_sig(response.url)} ({e})"
            )
            pass
    if not html_body:
        html_body = _fetch_html_body(response.url, impersonate)
    return html_body


def download_file(
    url,
    target,
    impersonate,
    mode="wb",
    chunk_size=8192,
    logevery=10,
    disallow_content_type="text/html",
):
    """
    Attempts to stream a download to an open target file handle in chunks. If the
    request returns a disallowed content type, then return a failed state with the
    response content.
    """
    text = True if "t" in mode else False
    data_streamed = 0
    last_log = 0
    r = requests.get(url, stream=True, impersonate=impersonate)
    try:
        # r.raise_for_status()
        if r.status_code != 200:
            raise DownloadBadStatusCode(f"Got non-200 status code: {r.status_code}")
        try:
            content_type = r.headers.get("Content-Type", "")
        except (ValueError, KeyError):
            content_type = ""
        content_type_parts = content_type.split(";")
        major_content_type = content_type_parts[0].strip()
        if major_content_type == disallow_content_type:
            html_body = _read_html_body(r, impersonate)
            if _is_expired_download_page(html_body):
                raise DownloadExpired(
                    "Download expired and requires email confirmation on Bandcamp"
                )
            raise DownloadInvalidContentType(
                f"Invalid content type: {major_content_type}"
            )
        try:
            content_length = int(r.headers.get("Content-Length", "0"))
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
                    log.info(f"Downloading {mask_sig(url)}: {percent_complete}%")
                    last_log = percent_complete
    finally:
        r.close()
    if data_streamed == 0:
        raise DownloadEmpty("Download was empty")
    return major_content_type


@contextmanager
def temporary_download_path(directory=None):
    """
    Provides a path for a temporary file, removed afterwards. The file is opened and closed
    by the caller as Windows can't open a file by name while it's already open.
    """
    file_descriptor, file_path = mkstemp(dir=directory)
    os.close(file_descriptor)
    try:
        yield Path(file_path)
    finally:
        Path(file_path).unlink(missing_ok=True)


def is_zip_file(file_path):
    try:
        with ZipFile(file_path) as z:
            z.infolist()
        return True
    except Exception:
        return False


def unzip_file(decompress_from, decompress_to):
    os.makedirs(decompress_to, exist_ok=True)
    try:
        with ZipFile(decompress_from) as z:
            infos = z.infolist()
            for info in infos:
                if "/" in info.filename or "\\" in info.filename:
                    raise DownloadUnexpectedLayout(
                        f"Download contains a directory: {info.filename}"
                    )
            used_names = set()
            for info in infos:
                # Only the name to extract to is changed, this doesn't affect reading it
                info.filename = unique_name(
                    fit_name(decompress_to, info.filename, keep_extension=True),
                    used_names,
                )
                z.extract(info, decompress_to)
    except (BadZipFile, EOFError, zlib.error) as e:
        raise DownloadCorrupt(f"Failed to decompress download: {e}") from e
    return True


def move_file(src, dst):
    return shutil.move(src, dst)


def copy_file(src, dst):
    return shutil.copyfile(src, dst)
