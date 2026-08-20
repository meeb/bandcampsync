"""Tests for bandcampsync.domain.sync.checkpoint."""

import json
from unittest.mock import Mock

from bandcampsync.domain.sync.checkpoint import (
    load_checkpoint,
    resolve_checkpoint_candidate,
    save_checkpoint,
    state_file_path,
)


def test_load_checkpoint_missing_file_returns_none(tmp_path):
    assert load_checkpoint(tmp_path) is None


def test_load_checkpoint_invalid_json_returns_none(tmp_path):
    state_file_path(tmp_path).write_text("not json")

    assert load_checkpoint(tmp_path) is None


def test_load_checkpoint_missing_token_returns_none(tmp_path):
    state_file_path(tmp_path).write_text(json.dumps({"version": 1}))

    assert load_checkpoint(tmp_path) is None


def test_load_checkpoint_returns_token(tmp_path):
    state_file_path(tmp_path).write_text(json.dumps({"last_seen_token": "abc"}))

    assert load_checkpoint(tmp_path) == "abc"


def test_save_checkpoint_writes_state(tmp_path):
    item = Mock(item_id=123, purchased="06 Feb 2026 19:06:47 GMT")

    save_checkpoint(tmp_path, item, "new-token")

    state = json.loads(state_file_path(tmp_path).read_text())
    assert state["last_seen_token"] == "new-token"
    assert state["last_seen_item_id"] == 123


def test_save_checkpoint_round_trips_through_load(tmp_path):
    item = Mock(item_id=1, purchased=None)

    save_checkpoint(tmp_path, item, "the-token")

    assert load_checkpoint(tmp_path) == "the-token"


def test_resolve_checkpoint_candidate_prefers_collection_items():
    purchases = [Mock(token="purchase-token")]
    collection_items = [Mock(token="collection-token")]

    candidate = resolve_checkpoint_candidate(purchases, collection_items)

    assert candidate is not None
    _, token = candidate
    assert token == "collection-token"


def test_resolve_checkpoint_candidate_falls_back_to_purchases():
    purchases = [Mock(token="purchase-token")]

    candidate = resolve_checkpoint_candidate(purchases, [])

    assert candidate is not None
    _, token = candidate
    assert token == "purchase-token"


def test_resolve_checkpoint_candidate_none_when_nothing_to_checkpoint():
    assert resolve_checkpoint_candidate([], []) is None


def test_resolve_checkpoint_candidate_none_when_no_usable_token():
    purchases = [Mock(token=None)]

    assert resolve_checkpoint_candidate(purchases, []) is None
