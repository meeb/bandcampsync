"""Tests for bandcampsync.domain.ignore_entry.actions."""

import logging
from unittest.mock import patch

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.ignore_entry import IgnoreFileLayout, IgnoreFileWriter
from bandcampsync.domain.ignore_entry.actions import record_ignored_item


def _item(item_id=1, band_name="Band", item_title="Item"):
    return BandcampItem(item_id=item_id, band_name=band_name, item_title=item_title)


def _layout_from(ign_file_path, insert_index):
    return IgnoreFileLayout(
        lines=ign_file_path.read_text().splitlines(keepends=True), insert_index=insert_index
    )


def test_record_ignored_item_writes_the_new_id_into_the_managed_section(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text(
        "# header\n# ==========================================================\n"
    )
    layout = _layout_from(ign_file_path, insert_index=2)
    item = _item(item_id=99, band_name="Band", item_title="Item")

    record_ignored_item(ign_file_path, layout, item)

    content = ign_file_path.read_text()
    assert "99  # Band / Item" in content


def test_writer_appends_each_call_directly_below_the_previous_one(tmp_path):
    # Items are added in the order they're downloaded (newest purchase
    # first), so the first record() call ends up topmost, closest to the
    # delimiter, with each subsequent call appended right below it.
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text("# ==========================================================\n")
    layout = _layout_from(ign_file_path, insert_index=1)
    writer = IgnoreFileWriter(ign_file_path=ign_file_path, layout=layout)

    writer.record(_item(item_id=1))
    writer.record(_item(item_id=2))

    lines_after_delimiter = ign_file_path.read_text().splitlines()[1:]
    assert lines_after_delimiter[0].startswith("1")
    assert lines_after_delimiter[1].startswith("2")


def test_writer_is_a_noop_without_an_ignore_file():
    writer = IgnoreFileWriter(ign_file_path=None, layout=IgnoreFileLayout())

    writer.record(_item())  # must not raise
    assert writer.layout == IgnoreFileLayout()


def test_record_ignored_item_logs_but_does_not_raise_when_the_write_fails(tmp_path, caplog):
    ign_file_path = tmp_path / "ignores.txt"
    layout = IgnoreFileLayout(
        lines=["# ==========================================================\n"], insert_index=1
    )
    caplog.set_level(logging.ERROR, logger="ignores")

    with patch(
        "bandcampsync.domain.ignore_entry.actions.atomic_write_text",
        side_effect=OSError("disk full"),
    ):
        record_ignored_item(ign_file_path, layout, _item(item_id=1))  # must not raise

    assert any("disk full" in r.message or r.exc_text for r in caplog.records if r.exc_info)
