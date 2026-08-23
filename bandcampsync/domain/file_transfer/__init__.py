"""Generic URL-to-disk transport: streaming a response to a file,
zip archives, local file moves/copies, and masking signed URLs for logs.
"""

from bandcampsync.domain.file_transfer.archive import extract_zip_archive, is_zip_archive
from bandcampsync.domain.file_transfer.errors import TransferBadStatusCode, TransferContentRejected
from bandcampsync.domain.file_transfer.local_copy import copy_file, move_file
from bandcampsync.domain.file_transfer.response_body import (
    read_response_body,
    refetch_response_body,
)
from bandcampsync.domain.file_transfer.stream_to_file import stream_url_to_file
from bandcampsync.domain.file_transfer.url_masking import mask_signed_url

__all__ = [
    "TransferBadStatusCode",
    "TransferContentRejected",
    "copy_file",
    "extract_zip_archive",
    "is_zip_archive",
    "mask_signed_url",
    "move_file",
    "read_response_body",
    "refetch_response_body",
    "stream_url_to_file",
]
