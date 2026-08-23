"""Tests for FanCollectionMixin.load_purchases."""

from unittest.mock import Mock

import pytest

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.interface.bandcamp import Bandcamp


@pytest.fixture
def bandcamp() -> Bandcamp:
    instance = Bandcamp("identity=test")
    instance.is_authenticated = True
    instance.user_id = 1
    return instance


def _item_data(item_id, band_name="Band", item_title="Item", token="t", **overrides):  # noqa: S107
    data = {
        "item_id": item_id,
        "band_name": band_name,
        "item_title": item_title,
        "item_type": "album",
        "token": token,
        "sale_item_type": "a",
        "sale_item_id": item_id,
    }
    data.update(overrides)
    return data


def _page(items, redownload_urls=None):
    return {"items": items, "redownload_urls": redownload_urls or {}}


def test_raises_when_not_authenticated():
    bandcamp = Bandcamp("identity=test")
    bandcamp.is_authenticated = False

    with pytest.raises(BandcampError, match="Authentication not verified"):
        bandcamp.load_purchases()


def test_empty_first_page_yields_no_purchases(bandcamp):
    bandcamp.request = Mock(return_value=_page([]))

    bandcamp.load_purchases()

    assert bandcamp.purchases == []
    assert bandcamp.collection_items == []


def test_raises_when_items_key_missing(bandcamp):
    bandcamp.request = Mock(return_value={"redownload_urls": {}})

    with pytest.raises(BandcampError, match="items"):
        bandcamp.load_purchases()


def test_raises_when_redownload_urls_key_missing(bandcamp):
    bandcamp.request = Mock(return_value={"items": [_item_data(1)]})

    with pytest.raises(BandcampError, match="redownload_urls"):
        bandcamp.load_purchases()


def test_skips_item_missing_band_name(bandcamp):
    item = _item_data(1, band_name=None)
    bandcamp.request = Mock(side_effect=[_page([item]), _page([])])

    bandcamp.load_purchases()

    assert bandcamp.purchases == []
    assert bandcamp.collection_items == []


def test_skips_item_missing_item_title(bandcamp):
    item = _item_data(1, item_title=None)
    bandcamp.request = Mock(side_effect=[_page([item]), _page([])])

    bandcamp.load_purchases()

    assert bandcamp.collection_items == []


def test_skips_item_missing_item_id(bandcamp):
    item = _item_data(1)
    del item["item_id"]
    bandcamp.request = Mock(side_effect=[_page([item]), _page([])])

    bandcamp.load_purchases()

    assert bandcamp.collection_items == []


def test_item_with_no_resolvable_download_url_is_a_collection_item_but_not_a_purchase(bandcamp):
    item = _item_data(1)
    bandcamp.request = Mock(side_effect=[_page([item], redownload_urls={}), _page([])])

    bandcamp.load_purchases()

    assert len(bandcamp.collection_items) == 1
    assert bandcamp.purchases == []


def test_item_with_resolvable_download_url_becomes_a_purchase(bandcamp):
    item = _item_data(1)
    bandcamp.request = Mock(
        side_effect=[
            _page([item], redownload_urls={"a1": "https://example.com/dl"}),
            _page([]),
        ]
    )

    bandcamp.load_purchases()

    assert len(bandcamp.purchases) == 1
    assert bandcamp.purchases[0].download_url == "https://example.com/dl"


def test_stop_when_halts_pagination_after_matching_item(bandcamp):
    matching_item = _item_data(1)
    later_item = _item_data(2)
    bandcamp.request = Mock(
        return_value=_page(
            [matching_item, later_item],
            redownload_urls={"a1": "https://example.com/1", "a2": "https://example.com/2"},
        )
    )

    bandcamp.load_purchases(stop_when=lambda item: item.item_id == 1)

    assert [item.item_id for item in bandcamp.collection_items] == [1]
    assert bandcamp.purchases == []
    bandcamp.request.assert_called_once()


def test_pagination_advances_token_across_pages(bandcamp):
    item_page_1 = _item_data(1, token="page1-token")
    item_page_2 = _item_data(2, token="page2-token")
    bandcamp.request = Mock(
        side_effect=[
            _page([item_page_1], redownload_urls={"a1": "https://example.com/1"}),
            _page([item_page_2], redownload_urls={"a2": "https://example.com/2"}),
            _page([]),
        ]
    )

    bandcamp.load_purchases()

    assert len(bandcamp.purchases) == 2
    assert bandcamp.request.call_count == 3
    second_call_data = bandcamp.request.call_args_list[1].kwargs["json_data"]
    assert second_call_data["older_than_token"] == "page1-token"


def test_deduplicates_purchases_sharing_band_and_title(bandcamp):
    item_a = _item_data(1, band_name="Band", item_title="Album")
    item_b = _item_data(2, band_name="Band", item_title="Album")
    bandcamp.request = Mock(
        side_effect=[
            _page(
                [item_a, item_b],
                redownload_urls={"a1": "https://example.com/1", "a2": "https://example.com/2"},
            ),
            _page([]),
        ]
    )

    bandcamp.load_purchases()

    assert [item.folder_suffix for item in bandcamp.purchases] == [" [1]", " [2]"]
