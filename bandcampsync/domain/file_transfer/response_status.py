from typing import Any

from bandcampsync.domain.file_transfer.errors import TransferBadStatusCode


def raise_if_bad_status(response: Any) -> None:
    if response.status_code != 200:
        raise TransferBadStatusCode(f"Got non-200 status code: {response.status_code}")
