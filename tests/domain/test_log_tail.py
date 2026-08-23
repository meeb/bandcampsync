"""Tests for bandcampsync.domain.log_tail."""

import logging

from bandcampsync.domain.log_tail import LogTail


def test_log_tail_keeps_only_the_most_recent_lines() -> None:
    log_tail = LogTail(capacity=3)
    logger_name = "bandcampsync.test.log_tail"

    logger = logging.getLogger(logger_name)
    logger.addHandler(log_tail)
    logger.setLevel(logging.INFO)
    for i in range(5):
        logger.info(f"line {i}")

    tail = log_tail.tail()
    assert len(tail) == 3
    assert "line 4" in tail[-1]
    assert "line 2" in tail[0]
