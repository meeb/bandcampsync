"""Tests for bandcampsync.interface.file_transfer.response_body."""

from unittest.mock import Mock, patch

from curl_cffi import requests

import bandcampsync.interface.file_transfer.response_body as response_body_module
from bandcampsync.interface.file_transfer.response_body import (
    read_response_body,
    refetch_response_body,
)


def test_read_response_body_returns_text_when_present():
    response = Mock(text="<html>hi</html>", url="https://example.com")
    assert read_response_body(response) == "<html>hi</html>"


def test_read_response_body_falls_back_to_decoded_content_when_text_is_empty():
    response = Mock(text="", content=b"raw bytes", url="https://example.com")
    assert read_response_body(response) == "raw bytes"


def test_read_response_body_refetches_when_everything_else_is_empty():
    response = Mock(text="", content=b"", url="https://example.com")

    with patch.object(response_body_module, "refetch_response_body", return_value="refetched"):
        assert read_response_body(response) == "refetched"


def test_read_response_body_returns_empty_string_when_text_access_raises():
    class RaisingTextResponse:
        url = "https://example.com"
        content = b""

        @property
        def text(self):
            raise requests.exceptions.RequestException("boom")

    with patch.object(response_body_module, "refetch_response_body", return_value=""):
        assert read_response_body(RaisingTextResponse()) == ""


def test_refetch_response_body_returns_empty_string_for_empty_url():
    assert refetch_response_body("") == ""


def test_refetch_response_body_returns_fetched_text():
    fetched = Mock(text="fetched content")
    with patch.object(response_body_module.requests, "get", return_value=fetched) as mock_get:
        assert refetch_response_body("https://example.com/f") == "fetched content"

    mock_get.assert_called_once_with("https://example.com/f", stream=False, impersonate="chrome")
    fetched.close.assert_called_once()


def test_refetch_response_body_returns_empty_string_on_request_failure():
    with patch.object(
        response_body_module.requests,
        "get",
        side_effect=requests.exceptions.RequestException("boom"),
    ):
        assert refetch_response_body("https://example.com/f") == ""
