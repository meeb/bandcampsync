from typing import IO, Any

from curl_cffi import requests

from bandcampsync.domain.file_transfer.content_type_check import (
    major_content_type_of,
    raise_if_content_type_disallowed,
)
from bandcampsync.domain.file_transfer.response_status import raise_if_bad_status
from bandcampsync.domain.file_transfer.write_chunks import write_response_chunks_to_file


def stream_url_to_file(
    url: str,
    target: IO[Any],
    mode: str = "wb",
    chunk_size: int = 8192,
    logevery: int = 10,
    disallow_content_type: str = "text/html",
) -> str:
    """Streams a URL to an open target file handle in chunks.

    Raises TransferContentRejected, body attached, on a disallowed content type.
    """
    response = requests.get(url, stream=True, impersonate="chrome")
    try:
        raise_if_bad_status(response)
        major_content_type = major_content_type_of(response)
        raise_if_content_type_disallowed(response, disallow_content_type, major_content_type)
        write_response_chunks_to_file(response, target, url, mode, chunk_size, logevery)
    finally:
        response.close()
    return major_content_type
