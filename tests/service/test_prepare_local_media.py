"""Tests for bandcampsync.service.prepare_local_media."""

import json
from datetime import date

from bandcampsync.domain.collection.checkpoint import state_file_path
from bandcampsync.domain.ignore_entry import IgnoreFileLayout, IgnoreFileWriter, IgnoreRules
from bandcampsync.domain.options import BandcampSyncOptions
from bandcampsync.service.prepare_local_media import prepare_local_media


def _options(tmp_path, **overrides):
    defaults = {
        "cookies": "identity=test",
        "dir_path": tmp_path,
        "media_format": "flac",
        "temp_dir_root": tmp_path,
        "ign_file_path": None,
        "ign_patterns": "",
        "notify_url": None,
    }
    defaults.update(overrides)
    return BandcampSyncOptions(**defaults)


def _ignore_rules():
    return IgnoreRules()


def _ignore_file_writer():
    return IgnoreFileWriter(ign_file_path=None, layout=IgnoreFileLayout())


def test_no_checkpoint_indexes_local_media(tmp_path):
    local_media, checkpoint_token, use_collection_checkpoint = prepare_local_media(
        _options(tmp_path), _ignore_rules(), _ignore_file_writer()
    )

    assert checkpoint_token is None
    assert use_collection_checkpoint is True
    assert local_media.media == {}


def test_checkpoint_present_skips_initial_local_media_index(tmp_path):
    state_file_path(tmp_path).write_text(json.dumps({"last_seen_token": "checkpoint-token"}))
    item_dir = tmp_path / "Band" / "Album"
    item_dir.mkdir(parents=True)
    (item_dir / "bandcamp_item_id.txt").write_text("123\n")

    local_media, checkpoint_token, use_collection_checkpoint = prepare_local_media(
        _options(tmp_path), _ignore_rules(), _ignore_file_writer()
    )

    assert checkpoint_token == "checkpoint-token"
    assert use_collection_checkpoint is True
    # index_on_init was False, so the on-disk item isn't picked up eagerly.
    assert local_media.media == {}


def test_until_date_ignores_checkpoint_even_if_present(tmp_path):
    state_file_path(tmp_path).write_text(json.dumps({"last_seen_token": "checkpoint-token"}))

    _, checkpoint_token, use_collection_checkpoint = prepare_local_media(
        _options(tmp_path, until_date=date(2026, 1, 1)), _ignore_rules(), _ignore_file_writer()
    )

    assert checkpoint_token is None
    assert use_collection_checkpoint is False
