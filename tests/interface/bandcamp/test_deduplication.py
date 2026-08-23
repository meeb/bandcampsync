"""Tests for bandcampsync.interface.bandcamp.deduplication."""

from bandcampsync.domain.bandcamp import BandcampItem
from bandcampsync.interface.bandcamp.deduplication import deduplicate_purchases


def _item(item_id, **overrides):
    data = {
        "item_id": item_id,
        "band_name": "Band",
        "item_title": "Album",
        "item_type": "album",
        "download_url": "https://example.com/download",
        "sale_item_type": "a",
        "sale_item_id": item_id,
    }
    data.update(overrides)
    return BandcampItem(data)


def test_leaves_unique_groups_untouched():
    item = _item(1)
    deduplicate_purchases({"key": [item]})

    assert item.folder_suffix == ""


def test_adds_item_id_suffix_to_every_duplicate():
    items = [_item(1), _item(2), _item(3)]
    deduplicate_purchases({"key": items})

    assert [item.folder_suffix for item in items] == [" [1]", " [2]", " [3]"]


def test_leaves_other_groups_untouched():
    unique = _item(1)
    duplicates = [_item(2), _item(3)]
    deduplicate_purchases({"unique": [unique], "dupes": duplicates})

    assert unique.folder_suffix == ""
    assert [item.folder_suffix for item in duplicates] == [" [2]", " [3]"]


def test_handles_multiple_duplicate_groups_independently():
    group_a = [_item(1), _item(2)]
    group_b = [_item(3), _item(4)]
    deduplicate_purchases({"a": group_a, "b": group_b})

    assert [item.folder_suffix for item in group_a] == [" [1]", " [2]"]
    assert [item.folder_suffix for item in group_b] == [" [3]", " [4]"]
