"""Tests for bandcampsync.domain.ignore_entry.index."""

from unittest.mock import patch

import pytest

from bandcampsync.domain.ignore_entry import load_ignore_rules


def test_no_ignore_file_returns_empty_rules():
    rules, layout = load_ignore_rules(None, "")

    assert rules.ids == frozenset()
    assert layout.lines == []


def test_missing_ignore_file_is_created_from_the_template(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"

    def fake_copyfile(_src, dst):
        from pathlib import Path

        Path(dst).write_text("# ==========================================================\n")

    with patch(
        "bandcampsync.domain.ignore_entry.index.shutil.copyfile", side_effect=fake_copyfile
    ) as mock_copy:
        rules, _layout = load_ignore_rules(ign_file_path, "")

    mock_copy.assert_called_once()
    assert mock_copy.call_args[0][1] == ign_file_path
    assert rules.ids == frozenset()


def test_parses_ids_below_the_delimiter(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text(
        "# some header\n"
        "# ==========================================================\n"
        "123  # Band / Album\n"
        "456  # Other Band / Other Album\n"
    )

    rules, _layout = load_ignore_rules(ign_file_path, "")

    assert rules.ids == frozenset({123, 456})


def test_parses_band_patterns():
    rules, _layout = load_ignore_rules(None, "Some Band Other")

    assert rules.band_patterns == ("some", "band", "other")


def test_appends_delimiter_section_when_missing(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text("# just a header, no delimiter\n")

    _rules, layout = load_ignore_rules(ign_file_path, "")

    assert any("=====" in line for line in layout.lines)
    assert layout.insert_index == len(layout.lines)


def test_invalid_id_line_raises_value_error(tmp_path):
    ign_file_path = tmp_path / "ignores.txt"
    ign_file_path.write_text(
        "# ==========================================================\nnot-a-number\n"
    )

    with pytest.raises(ValueError, match="not-a-number"):
        load_ignore_rules(ign_file_path, "")
