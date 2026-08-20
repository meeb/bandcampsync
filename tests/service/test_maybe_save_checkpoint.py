"""Tests for bandcampsync.service.maybe_save_checkpoint."""

import json
from unittest.mock import Mock

from bandcampsync.domain.sync.checkpoint import state_file_path
from bandcampsync.service.maybe_save_checkpoint import maybe_save_checkpoint


def test_skips_when_not_using_checkpoint(tmp_path):
    maybe_save_checkpoint(tmp_path, False, False, False, [Mock(token="t")], [])

    assert not state_file_path(tmp_path).exists()


def test_skips_during_dry_run(tmp_path):
    maybe_save_checkpoint(tmp_path, True, True, False, [Mock(token="t")], [])

    assert not state_file_path(tmp_path).exists()


def test_skips_when_had_errors(tmp_path):
    maybe_save_checkpoint(tmp_path, True, False, True, [Mock(token="t")], [])

    assert not state_file_path(tmp_path).exists()


def test_writes_checkpoint_from_purchases(tmp_path):
    purchases = [Mock(token="new-token", item_id=123, purchased="06 Feb 2026 19:06:47 GMT")]

    maybe_save_checkpoint(tmp_path, True, False, False, purchases, [])

    state = json.loads(state_file_path(tmp_path).read_text())
    assert state["last_seen_token"] == "new-token"
    assert state["last_seen_item_id"] == 123


def test_writes_checkpoint_from_newest_collection_item(tmp_path):
    collection_items = [
        Mock(token="physical-token", item_id=456, purchased="07 Feb 2026 19:06:47 GMT")
    ]

    maybe_save_checkpoint(tmp_path, True, False, False, [], collection_items)

    state = json.loads(state_file_path(tmp_path).read_text())
    assert state["last_seen_token"] == "physical-token"
    assert state["last_seen_item_id"] == 456
