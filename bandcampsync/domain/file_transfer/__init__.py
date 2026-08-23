"""Local file operations and pure helpers used across the download pipeline:
zip archives, local file moves/copies, masking signed URLs for logs, and the
transfer-specific exception types. No HTTP here - that's
interface/file_transfer, which actually talks to a remote server.
"""

from bandcampsync.domain.file_transfer.archive import extract_zip_archive, is_zip_archive
from bandcampsync.domain.file_transfer.errors import TransferBadStatusCode, TransferContentRejected
from bandcampsync.domain.file_transfer.local_copy import copy_file, move_file
from bandcampsync.domain.file_transfer.url_masking import mask_signed_url

__all__ = [
    "TransferBadStatusCode",
    "TransferContentRejected",
    "copy_file",
    "extract_zip_archive",
    "is_zip_archive",
    "mask_signed_url",
    "move_file",
]
