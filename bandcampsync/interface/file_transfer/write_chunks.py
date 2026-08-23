import math
from typing import IO, Any

from bandcampsync.domain.file_transfer.url_masking import mask_signed_url
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.domain.utils import header_or_default

log = get_logger("file_transfer")


def content_length_of(response: Any) -> int:
    content_length_header = header_or_default(response, "Content-Length", "0")
    try:
        return int(content_length_header)
    except ValueError:
        return 0


def write_response_chunks_to_file(
    response: Any,
    target: IO[Any],
    url: str,
    mode: str,
    chunk_size: int,
    logevery: int,
) -> None:
    write_as_text = "t" in mode
    content_length = content_length_of(response)
    bytes_streamed = 0
    last_logged_percent = 0
    for chunk in response.iter_content(chunk_size=chunk_size):
        bytes_streamed += len(chunk)
        target.write(chunk.decode() if write_as_text else chunk)
        if content_length > 0 and logevery > 0:
            percent_complete = math.floor((bytes_streamed / content_length) * 100)
            if percent_complete % logevery == 0 and percent_complete > last_logged_percent:
                log.info(f"Streaming {mask_signed_url(url)}: {percent_complete}%")
                last_logged_percent = percent_complete
