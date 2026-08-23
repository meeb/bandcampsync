"""Tests for bandcampsync.domain.file_transfer.response_status."""

from unittest.mock import Mock

import pytest

from bandcampsync.domain.file_transfer.errors import TransferBadStatusCode
from bandcampsync.domain.file_transfer.response_status import raise_if_bad_status


def test_raise_if_bad_status_is_a_noop_on_200():
    raise_if_bad_status(Mock(status_code=200))


def test_raise_if_bad_status_raises_on_non_200():
    with pytest.raises(TransferBadStatusCode):
        raise_if_bad_status(Mock(status_code=404))
