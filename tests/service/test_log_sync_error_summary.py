"""Tests for bandcampsync.service.log_sync_error_summary."""

import logging

from bandcampsync.service.log_sync_error_summary import log_sync_error_summary


def test_no_errors_logs_nothing(caplog):
    caplog.set_level(logging.WARNING, logger="sync")

    log_sync_error_summary([])

    assert caplog.records == []


def test_logs_summary_and_each_error(caplog):
    caplog.set_level(logging.WARNING, logger="sync")

    log_sync_error_summary(["first failure", "second failure"])

    messages = [r.message for r in caplog.records]
    assert "2 error(s)" in messages[0]
    assert "first failure" in messages[1]
    assert "second failure" in messages[2]
