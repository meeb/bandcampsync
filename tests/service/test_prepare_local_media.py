"""Tests for bandcampsync.service.prepare_local_media."""

import json
from datetime import date

from bandcampsync.domain.collection.checkpoint import state_file_path
from bandcampsync.service.prepare_local_media import prepare_local_media


def test_no_checkpoint_indexes_local_media(
    sync_options_factory, ignore_rules_factory, ignore_file_writer_factory
):
    local_media, checkpoint_token, use_collection_checkpoint = prepare_local_media(
        sync_options_factory(), ignore_rules_factory(), ignore_file_writer_factory()
    )

    assert checkpoint_token is None
    assert use_collection_checkpoint is True
    assert local_media.media == {}


def test_checkpoint_present_skips_initial_local_media_index(
    tmp_path, sync_options_factory, ignore_rules_factory, ignore_file_writer_factory
):
    state_file_path(tmp_path).write_text(json.dumps({"last_seen_token": "checkpoint-token"}))
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / "bandcamp_item_id.txt").write_text("123\n")

    local_media, checkpoint_token, use_collection_checkpoint = prepare_local_media(
        sync_options_factory(), ignore_rules_factory(), ignore_file_writer_factory()
    )

    assert checkpoint_token == "checkpoint-token"
    assert use_collection_checkpoint is True
    # index_on_init was False, so the on-disk item isn't picked up eagerly.
    assert local_media.media == {}


def test_until_date_ignores_checkpoint_even_if_present(
    tmp_path, sync_options_factory, ignore_rules_factory, ignore_file_writer_factory
):
    state_file_path(tmp_path).write_text(json.dumps({"last_seen_token": "checkpoint-token"}))

    _, checkpoint_token, use_collection_checkpoint = prepare_local_media(
        sync_options_factory(until_date=date(2026, 1, 1)),
        ignore_rules_factory(),
        ignore_file_writer_factory(),
    )

    assert checkpoint_token is None
    assert use_collection_checkpoint is False
