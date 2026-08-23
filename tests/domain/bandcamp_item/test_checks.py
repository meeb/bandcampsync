"""Tests for bandcampsync.domain.bandcamp_item.checks."""

import json
from pathlib import Path

import pytest

from bandcampsync.domain.bandcamp_item import BandcampItem, is_physical_purchase


def _load_payload(name):
    fixture_path = Path(__file__).resolve().parent / "data" / name
    return json.loads(fixture_path.read_text(encoding="utf-8", errors="ignore"))


@pytest.fixture
def digital_item():
    return _load_payload("collection-item-digital-only.json")["items"][0]


@pytest.fixture
def physical_item():
    return _load_payload("collection-item-physical-only.json")["items"][0]


def test_is_physical_purchase_true(physical_item):
    assert is_physical_purchase(BandcampItem(**physical_item)) is True


def test_is_physical_purchase_false(digital_item):
    assert is_physical_purchase(BandcampItem(**digital_item)) is False
