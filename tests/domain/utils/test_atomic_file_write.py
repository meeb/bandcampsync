"""Tests for bandcampsync.domain.utils.atomic_file_write."""

from pathlib import Path

import pytest

from bandcampsync.domain.utils.atomic_file_write import atomic_write_text


def test_writes_content_to_target_path(tmp_path: Path):
    target = tmp_path / "state.json"

    atomic_write_text(target, "hello")

    assert target.read_text() == "hello"


def test_replaces_existing_content(tmp_path: Path):
    target = tmp_path / "state.json"
    target.write_text("old")

    atomic_write_text(target, "new")

    assert target.read_text() == "new"


def test_leaves_no_tmp_file_behind_on_success(tmp_path: Path):
    target = tmp_path / "state.json"

    atomic_write_text(target, "hello")

    assert list(tmp_path.iterdir()) == [target]


def test_cleans_up_tmp_file_and_reraises_on_failure(tmp_path: Path):
    target = tmp_path / "missing_dir" / "state.json"

    with pytest.raises(FileNotFoundError):
        atomic_write_text(target, "hello")

    assert not list(tmp_path.glob("*.tmp"))
