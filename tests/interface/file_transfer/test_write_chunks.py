"""Tests for bandcampsync.interface.file_transfer.write_chunks."""

from io import BytesIO
from unittest.mock import Mock

from bandcampsync.interface.file_transfer.write_chunks import (
    content_length_of,
    write_response_chunks_to_file,
)


def test_content_length_of_parses_the_header():
    response = Mock(headers={"Content-Length": "1024"})
    assert content_length_of(response) == 1024


def test_content_length_of_defaults_to_zero_when_missing():
    response = Mock(headers={})
    assert content_length_of(response) == 0


def test_content_length_of_defaults_to_zero_when_unparseable():
    response = Mock(headers={"Content-Length": "not-a-number"})
    assert content_length_of(response) == 0


def test_write_response_chunks_to_file_writes_all_bytes():
    response = Mock(headers={})
    response.iter_content.return_value = [b"abc", b"def"]
    target = BytesIO()

    write_response_chunks_to_file(
        response, target, "https://example.com/f", mode="wb", chunk_size=8192, logevery=0
    )

    assert target.getvalue() == b"abcdef"


def test_write_response_chunks_to_file_decodes_when_writing_text():
    response = Mock(headers={})
    response.iter_content.return_value = [b"hello"]
    target = Mock()

    write_response_chunks_to_file(
        response, target, "https://example.com/f", mode="wt", chunk_size=8192, logevery=0
    )

    target.write.assert_called_once_with("hello")


def test_write_response_chunks_to_file_logs_progress_at_configured_intervals(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="file_transfer")
    response = Mock(headers={"Content-Length": "100"})
    response.iter_content.return_value = [b"x" * 50, b"x" * 50]
    target = BytesIO()

    write_response_chunks_to_file(
        response, target, "https://example.com/f", mode="wb", chunk_size=8192, logevery=50
    )

    progress_logs = [r for r in caplog.records if "Streaming" in r.message]
    assert len(progress_logs) == 2
    assert "50%" in progress_logs[0].message
    assert "100%" in progress_logs[1].message
