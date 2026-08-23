"""Tests for bandcampsync.domain.file_transfer.content_type_check."""

from unittest.mock import Mock

import pytest

from bandcampsync.domain.file_transfer.content_type_check import (
    major_content_type_of,
    raise_if_content_type_disallowed,
)
from bandcampsync.domain.file_transfer.errors import TransferContentRejected


def test_major_content_type_of_strips_charset_suffix():
    response = Mock(headers={"Content-Type": "text/html; charset=utf-8"})

    assert major_content_type_of(response) == "text/html"


def test_raise_if_content_type_disallowed_is_a_noop_when_type_is_allowed():
    response = Mock()

    raise_if_content_type_disallowed(response, "text/html", "audio/flac")


def test_raise_if_content_type_disallowed_carries_the_response_body():
    response = Mock(text="<html>expired</html>")

    with pytest.raises(TransferContentRejected) as excinfo:
        raise_if_content_type_disallowed(response, "text/html", "text/html")

    assert excinfo.value.content_type == "text/html"
    assert excinfo.value.body == "<html>expired</html>"
