"""Tests for bandcampsync.domain.utils.response_headers."""

from unittest.mock import Mock

from bandcampsync.domain.utils.response_headers import header_or_default


def test_returns_header_value_when_present():
    response = Mock(headers={"Content-Type": "audio/flac"})

    assert header_or_default(response, "Content-Type", "") == "audio/flac"


def test_returns_default_when_header_missing():
    response = Mock(headers={})

    assert header_or_default(response, "Content-Type", "text/plain") == "text/plain"


def test_returns_default_when_headers_access_raises():
    response = Mock()
    response.headers.get.side_effect = ValueError("boom")

    assert header_or_default(response, "Content-Type", "text/plain") == "text/plain"
