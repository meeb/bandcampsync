"""Tests for Ignores."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

import pytest

from bandcampsync.ignores import Ignores


def _item(item_id):
    return Mock(item_id=item_id, band_name="Band", item_title=f"Album {item_id}")


def test_add_is_kept_after_reload(tmp_path):
    ignore_file = tmp_path / "ignores.txt"
    ignore_file.write_text("1  # Band / Album 1\n")
    ignores = Ignores(ign_file_path=ignore_file, ign_patterns="")

    ignores.add(_item(2))
    ignores.add(_item(3))

    assert Ignores(ign_file_path=ignore_file, ign_patterns="").ids == {1, 2, 3}


def test_add_from_multiple_threads_keeps_every_item(tmp_path):
    ignore_file = tmp_path / "ignores.txt"
    ignore_file.write_text("# Ignored items\n")
    ignores = Ignores(ign_file_path=ignore_file, ign_patterns="")
    thread_count = 8
    items_per_thread = 40
    barrier = Barrier(thread_count)

    def add_items(thread_number):
        barrier.wait()
        for number in range(items_per_thread):
            ignores.add(_item(thread_number * 1000 + number))

    with ThreadPoolExecutor(thread_count) as pool:
        # Reading the results raises any exception from the threads
        list(pool.map(add_items, range(thread_count)))

    expected = {
        thread_number * 1000 + number
        for thread_number in range(thread_count)
        for number in range(items_per_thread)
    }
    assert Ignores(ign_file_path=ignore_file, ign_patterns="").ids == expected
    assert not (tmp_path / "ignores.txt.tmp").exists()


def test_missing_file_is_created_without_docker_template(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bandcampsync.ignores.TEMPLATE_IGNORES_FILE", str(tmp_path / "missing.txt")
    )
    ignore_file = tmp_path / "ignores.txt"

    ignores = Ignores(ign_file_path=ignore_file, ign_patterns="")
    ignores.add(_item(1))

    assert Ignores(ign_file_path=ignore_file, ign_patterns="").ids == {1}


def test_missing_file_is_created_from_docker_template(tmp_path, monkeypatch):
    template = tmp_path / "template.txt"
    template.write_text("# Template\n")
    monkeypatch.setattr("bandcampsync.ignores.TEMPLATE_IGNORES_FILE", str(template))
    ignore_file = tmp_path / "ignores.txt"

    Ignores(ign_file_path=ignore_file, ign_patterns="")

    assert ignore_file.read_text() == "# Template\n"


def test_names_are_read_as_utf8(tmp_path):
    ignore_file = tmp_path / "ignores.txt"
    ignore_file.write_bytes("1  # Band / \u28ce\u0338 Album\n".encode("utf-8"))

    ignores = Ignores(ign_file_path=ignore_file, ign_patterns="")

    assert ignores.ids == {1}
    assert ignores.is_name_used_by_other_item("Band / \u28ce\u0338 Album", 2) is True


@pytest.mark.parametrize(
    "title", ["Line one\nLine two", "Line one\r\nLine two", "One\rTwo"]
)
def test_line_breaks_in_names_do_not_break_the_file(tmp_path, title):
    ignore_file = tmp_path / "ignores.txt"
    ignore_file.write_text("# Ignored items\n")
    ignores = Ignores(ign_file_path=ignore_file, ign_patterns="")
    item = Mock(item_id=1, band_name="Band", item_title=title)

    ignores.add(item)
    reloaded = Ignores(ign_file_path=ignore_file, ign_patterns="")

    assert reloaded.ids == {1}
    assert reloaded.is_name_used_by_other_item(f"Band / {title}", 2) is True
