"""Tests for bandcampsync.domain.ignores.Ignores."""

from unittest.mock import patch

import pytest

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.ignores import Ignores


def _item(item_id=1, band_name="Band", item_title="Item"):
    return BandcampItem(item_id=item_id, band_name=band_name, item_title=item_title)


def test_no_ignore_file_means_nothing_is_ignored():
    ignores = Ignores(ign_file_path=None, ign_patterns="")

    assert ignores.ids == set()
    assert ignores.is_ignored(_item()) is False


def test_missing_ignore_file_is_created_from_the_template(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"

    def fake_copyfile(_src, dst):
        from pathlib import Path

        Path(dst).write_text("# ==========================================================\n")

    with patch(
        "bandcampsync.domain.ignores.shutil.copyfile", side_effect=fake_copyfile
    ) as mock_copy:
        ignores = Ignores(ign_file_path=ign_file_path, ign_patterns="")

    mock_copy.assert_called_once()
    assert mock_copy.call_args[0][1] == ign_file_path
    assert ignores.ids == set()


def test_parses_ids_below_the_delimiter(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text(
        "# some header\n"
        "# ==========================================================\n"
        "123  # Band / Album\n"
        "456  # Other Band / Other Album\n"
    )

    ignores = Ignores(ign_file_path=ign_file_path, ign_patterns="")

    assert ignores.ids == {123, 456}


def test_appends_delimiter_section_when_missing(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text("# just a header, no delimiter\n")

    ignores = Ignores(ign_file_path=ign_file_path, ign_patterns="")

    assert any("=====" in line for line in ignores.ign_lines)
    assert ignores.ign_insert_index == len(ignores.ign_lines)


def test_invalid_id_line_raises_value_error(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text(
        "# ==========================================================\nnot-a-number\n"
    )

    with pytest.raises(ValueError, match="not-a-number"):
        Ignores(ign_file_path=ign_file_path, ign_patterns="")


def test_add_writes_the_new_id_into_the_managed_section(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text(
        "# header\n# ==========================================================\n"
    )
    ignores = Ignores(ign_file_path=ign_file_path, ign_patterns="")

    ignores.add(_item(item_id=99, band_name="Band", item_title="Item"))

    content = ign_file_path.read_text()
    assert "99  # Band / Item" in content
    assert 99 not in ignores.ids  # add() only updates the file, not the in-memory id set


def test_add_appends_each_call_directly_below_the_previous_one(tmp_path):
    # Items are added in the order they're downloaded (newest purchase
    # first), so the first add() call ends up topmost, closest to the
    # delimiter, with each subsequent call appended right below it.
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text("# ==========================================================\n")
    ignores = Ignores(ign_file_path=ign_file_path, ign_patterns="")

    ignores.add(_item(item_id=1))
    ignores.add(_item(item_id=2))

    lines_after_delimiter = ign_file_path.read_text().splitlines()[1:]
    assert lines_after_delimiter[0].startswith("1")
    assert lines_after_delimiter[1].startswith("2")


def test_add_is_a_noop_without_an_ignore_file():
    ignores = Ignores(ign_file_path=None, ign_patterns="")

    ignores.add(_item())  # must not raise


def test_add_logs_but_does_not_raise_when_the_write_fails(tmp_path, caplog):
    import logging

    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text("# ==========================================================\n")
    ignores = Ignores(ign_file_path=ign_file_path, ign_patterns="")
    caplog.set_level(logging.ERROR, logger="ignores")

    with patch("bandcampsync.domain.ignores.atomic_write_text", side_effect=OSError("disk full")):
        ignores.add(_item(item_id=1))  # must not raise

    assert any("disk full" in r.message or r.exc_text for r in caplog.records if r.exc_info)


def test_is_ignored_by_id():
    ignores = Ignores(ign_file_path=None, ign_patterns="")
    ignores.ids = {1}

    assert ignores.is_ignored(_item(item_id=1)) is True
    assert ignores.is_ignored(_item(item_id=2)) is False


def test_is_ignored_by_band_pattern_case_insensitive():
    ignores = Ignores(ign_file_path=None, ign_patterns="Some Band")

    assert ignores.is_ignored(_item(band_name="a SOME BAND collective")) is True
    assert ignores.is_ignored(_item(band_name="Unrelated Artist")) is False
