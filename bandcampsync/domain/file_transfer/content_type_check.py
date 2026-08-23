from typing import Any

from bandcampsync.domain.file_transfer.errors import TransferContentRejected
from bandcampsync.domain.file_transfer.response_body import read_response_body
from bandcampsync.domain.utils import header_or_default


def major_content_type_of(response: Any) -> str:
    content_type_header = header_or_default(response, "Content-Type", "")
    return content_type_header.split(";")[0].strip()


def raise_if_content_type_disallowed(
    response: Any, disallowed_content_type: str, major_content_type: str
) -> None:
    if major_content_type != disallowed_content_type:
        return
    body = read_response_body(response)
    raise TransferContentRejected(
        f"Rejected content type: {major_content_type}", major_content_type, body
    )
