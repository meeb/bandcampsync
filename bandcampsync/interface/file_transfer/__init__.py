"""Streams a URL to disk over HTTP: the actual network transport half of
the download pipeline. Not Bandcamp-specific - domain/collection/
download_purchase depends on this only through the local-file/pure half
that stayed in domain/file_transfer (copy_file, move_file,
extract_zip_archive, is_zip_archive, mask_signed_url, and the shared
Transfer* exception types).
"""

from bandcampsync.interface.file_transfer.response_body import (
    read_response_body,
    refetch_response_body,
)
from bandcampsync.interface.file_transfer.stream_to_file import stream_url_to_file

__all__ = [
    "read_response_body",
    "refetch_response_body",
    "stream_url_to_file",
]
