import math
import shutil
from pathlib import Path
from typing import IO, Any
from zipfile import ZipFile

from bs4 import BeautifulSoup
from curl_cffi import requests

from bandcampsync.domain.download.errors import (
    DownloadBadStatusCode,
    DownloadExpired,
    DownloadInvalidContentType,
)
from bandcampsync.domain.logging_setup import get_logger

log = get_logger("download")


def mask_sig(url: str) -> str:
    if "&sig=" not in url:
        return url
    url_parts = url.split("&")
    for i, url_part in enumerate(url_parts):
        if url_part[:4] == "sig=":
            url_parts[i] = "sig=[masked]"
        elif url_part[:6] == "token=":
            url_parts[i] = "token=[masked]"
    return "&".join(url_parts)


def _is_expired_download_page(html: str) -> bool:
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    reauth_error = soup.select_one("div.email-reauth-error")
    if not reauth_error:
        return False
    style = str(reauth_error.get("style")) or ""
    style = style.replace(" ", "").lower()
    return "display:none" not in style


def _fetch_html_body(url: str) -> str:
    if not url:
        return ""
    try:
        resp = requests.get(url, stream=False, impersonate="chrome")
    except requests.exceptions.RequestException as e:
        log.warning(f"Failed to fetch HTML body for: {url} ({e})")
        return ""
    try:
        return resp.text or ""
    finally:
        resp.close()


def _read_html_body(response: Any) -> str:
    html_body = ""
    try:
        html_body = response.text or ""
    except requests.exceptions.RequestException as e:
        log.warning(f"Failed to read HTML body for: {response.url} ({e})")
    if not html_body:
        try:
            html_body = response.content.decode("utf-8", errors="replace")
        except requests.exceptions.RequestException as e:
            log.warning(f"Failed to decode HTML body for: {response.url} ({e})")
    if not html_body:
        html_body = _fetch_html_body(response.url)
    return html_body


def download_file(
    url: str,
    target: IO[Any],
    mode: str = "wb",
    chunk_size: int = 8192,
    logevery: int = 10,
    disallow_content_type: str = "text/html",
) -> str:
    """Streams a download to an open target file handle in chunks.

    If the request returns a disallowed content type, raises instead of
    writing it - that response body is inspected to distinguish an expired
    download link from any other unexpected content type.
    """
    text = "t" in mode
    data_streamed = 0
    last_log = 0
    r = requests.get(url, stream=True, impersonate="chrome")
    try:
        if r.status_code != 200:
            raise DownloadBadStatusCode(f"Got non-200 status code: {r.status_code}")
        try:
            content_type = r.headers.get("Content-Type", "")
        except (ValueError, KeyError):
            content_type = ""
        content_type_parts = content_type.split(";")
        major_content_type = content_type_parts[0].strip()
        if major_content_type == disallow_content_type:
            html_body = _read_html_body(r)
            if _is_expired_download_page(html_body):
                raise DownloadExpired(
                    "Download expired and requires email confirmation on Bandcamp"
                )
            raise DownloadInvalidContentType(f"Invalid content type: {major_content_type}")
        try:
            content_length = int(r.headers.get("Content-Length", "0"))
        except (ValueError, KeyError):
            content_length = 0
        for chunk in r.iter_content(chunk_size=chunk_size):
            data_streamed += len(chunk)
            target.write(chunk.decode() if text else chunk)
            if content_length > 0 and logevery > 0:
                percent_complete = math.floor((data_streamed / content_length) * 100)
                if percent_complete % logevery == 0 and percent_complete > last_log:
                    log.info(f"Downloading {mask_sig(url)}: {percent_complete}%")
                    last_log = percent_complete
    finally:
        r.close()
    return str(major_content_type)


def is_zip_file(file_path: Path) -> bool:
    try:
        with ZipFile(file_path) as z:
            z.infolist()
    except Exception:
        return False
    else:
        return True


def unzip_file(decompress_from: Path, decompress_to: Path) -> bool:
    with ZipFile(decompress_from) as z:
        z.extractall(decompress_to)
    return True


def move_file(src: Path, dst: Path) -> Path | str:
    return shutil.move(src, dst)


def copy_file(src: Path, dst: Path) -> Path | str:
    return shutil.copyfile(src, dst)
