"""Tests for bandcampsync.interface.bandcamp.download_resolution."""

import json
from pathlib import Path

import pytest

from bandcampsync.domain.bandcamp import BandcampItem
from bandcampsync.interface.bandcamp.download_resolution import resolve_download_url


def _load_payload(name):
    fixture_path = Path(__file__).resolve().parent / "data" / name
    return json.loads(fixture_path.read_text(encoding="utf-8", errors="ignore"))


def _download_key(item):
    return f"{item['sale_item_type']}{item['sale_item_id']}"


@pytest.fixture
def digital_payload():
    return _load_payload("collection-item-digital-only.json")


@pytest.fixture
def physical_payload():
    return _load_payload("collection-item-physical-only.json")


@pytest.fixture
def digital_item(digital_payload):
    return digital_payload["items"][0]


@pytest.fixture
def physical_item(physical_payload):
    return physical_payload["items"][0]


def test_resolve_download_url_digital(digital_payload, digital_item):
    item = BandcampItem(digital_item)

    download_url = resolve_download_url(item, digital_payload["redownload_urls"])

    expected_key = _download_key(digital_item)
    assert download_url == digital_payload["redownload_urls"][expected_key]


def test_resolve_download_url_physical(physical_payload, physical_item):
    item = BandcampItem(physical_item)

    download_url = resolve_download_url(item, physical_payload["redownload_urls"])

    assert download_url is None
