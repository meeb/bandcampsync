from typing import Any

from curl_cffi import requests

from bandcampsync.domain.logging_setup import get_logger

log = get_logger("file_transfer")


def refetch_response_body(url: str) -> str:
    if not url:
        return ""
    try:
        refetched_response = requests.get(url, stream=False, impersonate="chrome")
    except requests.exceptions.RequestException as request_error:
        log.warning(f"Failed to re-fetch response body for: {url} ({request_error})")
        return ""
    try:
        return refetched_response.text or ""
    finally:
        refetched_response.close()


def read_response_body(response: Any) -> str:
    body = ""
    try:
        body = response.text or ""
    except requests.exceptions.RequestException as request_error:
        log.warning(f"Failed to read response body for: {response.url} ({request_error})")
    if not body:
        try:
            body = response.content.decode("utf-8", errors="replace")
        except requests.exceptions.RequestException as request_error:
            log.warning(f"Failed to decode response body for: {response.url} ({request_error})")
    if not body:
        body = refetch_response_body(response.url)
    return body
