"""Tests for bandcampsync.service.log_id_file_migration_warning."""

import logging

from bandcampsync.service.log_id_file_migration_warning import (
    log_id_file_migration_warning_if_needed,
)


def test_skips_when_no_warning_needed(caplog):
    caplog.set_level(logging.WARNING, logger="sync")

    log_id_file_migration_warning_if_needed(False, False, None)

    assert caplog.records == []


def test_skips_when_running_sync_ignore_file_script(caplog):
    caplog.set_level(logging.WARNING, logger="sync")

    log_id_file_migration_warning_if_needed(True, True, None)

    assert caplog.records == []


def test_logs_warning_with_ign_file_path(caplog):
    caplog.set_level(logging.WARNING, logger="sync")

    log_id_file_migration_warning_if_needed(True, False, "/config/ignores.txt")

    assert len(caplog.records) == 1
    assert "/config/ignores.txt" in caplog.records[0].message
    assert "bandcamp_item_id.txt" in caplog.records[0].message
