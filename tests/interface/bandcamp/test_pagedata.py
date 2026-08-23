"""Tests for bandcampsync.interface.bandcamp.pagedata."""

import json

import pytest
from bs4 import BeautifulSoup

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.interface.bandcamp.pagedata import (
    extract_pagedata_from_html,
    extract_pagedata_from_soup,
)


def _html_with_blob(blob: dict, id_name: str = "pagedata") -> str:
    encoded = json.dumps(blob).replace('"', "&quot;")
    return f'<html><body><div id="{id_name}" data-blob="{encoded}"></div></body></html>'


def test_extracts_and_parses_the_json_blob():
    blob = {"digital_items": [{"item_id": 1}]}
    soup = BeautifulSoup(_html_with_blob(blob), "html.parser")

    assert extract_pagedata_from_soup(soup) == blob


def test_extracts_from_a_custom_id_name():
    blob = {"pageContext": {"identity": {"fanId": 1}}}
    soup = BeautifulSoup(_html_with_blob(blob, id_name="HomepageApp"), "html.parser")

    assert extract_pagedata_from_soup(soup, id_name="HomepageApp") == blob


def test_raises_when_the_div_is_missing():
    soup = BeautifulSoup("<html><body>no data here</body></html>", "html.parser")

    with pytest.raises(BandcampError, match="Failed to locate"):
        extract_pagedata_from_soup(soup)


def test_raises_when_data_blob_attribute_is_missing():
    soup = BeautifulSoup('<div id="pagedata"></div>', "html.parser")

    with pytest.raises(BandcampError, match="Failed to extract page data"):
        extract_pagedata_from_soup(soup)


def test_raises_when_data_blob_is_not_valid_json():
    soup = BeautifulSoup('<div id="pagedata" data-blob="not json"></div>', "html.parser")

    with pytest.raises(BandcampError, match="Failed to parse pagedata as JSON"):
        extract_pagedata_from_soup(soup)


def test_extract_pagedata_from_html_parses_raw_html_directly():
    blob = {"foo": "bar"}

    assert extract_pagedata_from_html(_html_with_blob(blob)) == blob
