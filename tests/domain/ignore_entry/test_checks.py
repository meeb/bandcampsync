"""Tests for bandcampsync.domain.ignore_entry.checks.

Pure - no filesystem involved, unlike the old Ignores class this replaces.
"""

from bandcampsync.domain.ignore_entry import IgnoreRules, is_ignored


def test_nothing_is_ignored_by_default():
    assert is_ignored(IgnoreRules(), 1, "Band", "Item") is False


def test_is_ignored_by_id():
    rules = IgnoreRules(ids=frozenset({1}))

    assert is_ignored(rules, 1, "Band", "Item") is True
    assert is_ignored(rules, 2, "Band", "Item") is False


def test_is_ignored_by_band_pattern_case_insensitive():
    rules = IgnoreRules(band_patterns=("some band",))

    assert is_ignored(rules, 1, "a SOME BAND collective", "Item") is True
    assert is_ignored(rules, 1, "Unrelated Artist", "Item") is False
