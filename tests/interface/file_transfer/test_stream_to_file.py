"""Tests for bandcampsync.interface.file_transfer.stream_to_file."""

from io import BytesIO
from unittest.mock import Mock, patch

import pytest

import bandcampsync.interface.file_transfer.stream_to_file as stream_to_file_module
from bandcampsync.domain.file_transfer.errors import TransferBadStatusCode, TransferContentRejected
from bandcampsync.interface.file_transfer.stream_to_file import stream_url_to_file


def _response(status_code=200, content_type="audio/flac", chunks=(b"data",)):
    response = Mock(status_code=status_code, headers={"Content-Type": content_type})
    response.iter_content.return_value = list(chunks)
    return response


def test_streams_response_body_and_returns_content_type():
    response = _response(chunks=(b"abc", b"def"))
    target = BytesIO()

    with patch.object(stream_to_file_module.requests, "get", return_value=response):
        content_type = stream_url_to_file("https://example.com/f", target)

    assert content_type == "audio/flac"
    assert target.getvalue() == b"abcdef"
    response.close.assert_called_once()


def test_raises_on_bad_status_code_and_still_closes_the_response():
    response = _response(status_code=404)

    with (
        patch.object(stream_to_file_module.requests, "get", return_value=response),
        pytest.raises(TransferBadStatusCode),
    ):
        stream_url_to_file("https://example.com/f", BytesIO())

    response.close.assert_called_once()


def test_raises_on_disallowed_content_type():
    response = _response(content_type="text/html")
    response.text = "<html>expired</html>"

    with (
        patch.object(stream_to_file_module.requests, "get", return_value=response),
        pytest.raises(TransferContentRejected) as excinfo,
    ):
        stream_url_to_file("https://example.com/f", BytesIO())

    assert excinfo.value.content_type == "text/html"


def test_custom_disallow_content_type_only_blocks_the_type_named():
    # The default disallowed type is text/html; here we swap it for
    # application/json, so a text/html response is allowed through.
    response = _response(content_type="text/html", chunks=(b"<html></html>",))
    target = BytesIO()

    with patch.object(stream_to_file_module.requests, "get", return_value=response):
        content_type = stream_url_to_file(
            "https://example.com/f", target, disallow_content_type="application/json"
        )

    assert content_type == "text/html"
    assert target.getvalue() == b"<html></html>"
