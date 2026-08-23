"""Tests for bandcampsync.domain.ignore_entry.checks.

Pure - no filesystem involved, unlike the old Ignores class this replaces.
"""

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.ignore_entry import IgnoreRules, is_ignored


def _item(item_id=1, band_name="Band", item_title="Item"):
    return BandcampItem(item_id=item_id, band_name=band_name, item_title=item_title)


def test_nothing_is_ignored_by_default():
    assert is_ignored(IgnoreRules(), _item()) is False


def test_is_ignored_by_id():
    rules = IgnoreRules(ids=frozenset({1}))

    assert is_ignored(rules, _item(item_id=1)) is True
    assert is_ignored(rules, _item(item_id=2)) is False


def test_is_ignored_by_band_pattern_case_insensitive():
    rules = IgnoreRules(band_patterns=("some band",))

    assert is_ignored(rules, _item(band_name="a SOME BAND collective")) is True
    assert is_ignored(rules, _item(band_name="Unrelated Artist")) is False
