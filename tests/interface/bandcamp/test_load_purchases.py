"""Tests for FanCollectionMixin.load_purchases."""

import pytest

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.interface.bandcamp import Bandcamp


def _page(items, redownload_urls=None):
    return {"items": items, "redownload_urls": redownload_urls or {}}


def test_authenticates_automatically_when_not_yet_authenticated(mocker):
    bandcamp = Bandcamp("identity=test")
    bandcamp.is_authenticated = False

    def fake_verify_authentication():
        bandcamp.is_authenticated = True
        bandcamp.user_id = 1
        return True

    bandcamp.verify_authentication = mocker.Mock(side_effect=fake_verify_authentication)
    bandcamp.request = mocker.Mock(return_value=_page([]))

    bandcamp.load_purchases()

    bandcamp.verify_authentication.assert_called_once()
    assert bandcamp.purchases == []


def test_empty_first_page_yields_no_purchases(mocker, bandcamp_client):
    bandcamp_client.request = mocker.Mock(return_value=_page([]))

    bandcamp_client.load_purchases()

    assert bandcamp_client.purchases == []
    assert bandcamp_client.collection_items == []


def test_raises_when_items_key_missing(mocker, bandcamp_client):
    bandcamp_client.request = mocker.Mock(return_value={"redownload_urls": {}})

    with pytest.raises(BandcampError, match="items"):
        bandcamp_client.load_purchases()


def test_raises_when_redownload_urls_key_missing(mocker, bandcamp_client, raw_item_factory):
    bandcamp_client.request = mocker.Mock(return_value={"items": [raw_item_factory(item_id=1)]})

    with pytest.raises(BandcampError, match="redownload_urls"):
        bandcamp_client.load_purchases()


def test_skips_item_missing_band_name(mocker, bandcamp_client, raw_item_factory):
    item = raw_item_factory(item_id=1)
    item["band_name"] = None
    bandcamp_client.request = mocker.Mock(side_effect=[_page([item]), _page([])])

    bandcamp_client.load_purchases()

    assert bandcamp_client.purchases == []
    assert bandcamp_client.collection_items == []


def test_skips_item_missing_item_title(mocker, bandcamp_client, raw_item_factory):
    item = raw_item_factory(item_id=1)
    item["item_title"] = None
    bandcamp_client.request = mocker.Mock(side_effect=[_page([item]), _page([])])

    bandcamp_client.load_purchases()

    assert bandcamp_client.collection_items == []


def test_skips_item_missing_item_id(mocker, bandcamp_client, raw_item_factory):
    item = raw_item_factory(item_id=1)
    del item["item_id"]
    bandcamp_client.request = mocker.Mock(side_effect=[_page([item]), _page([])])

    bandcamp_client.load_purchases()

    assert bandcamp_client.collection_items == []


def test_item_with_no_resolvable_download_url_is_a_collection_item_but_not_a_purchase(
    mocker, bandcamp_client, raw_item_factory
):
    item = raw_item_factory(item_id=1)
    bandcamp_client.request = mocker.Mock(
        side_effect=[_page([item], redownload_urls={}), _page([])]
    )

    bandcamp_client.load_purchases()

    assert len(bandcamp_client.collection_items) == 1
    assert bandcamp_client.purchases == []


def test_item_with_resolvable_download_url_becomes_a_purchase(
    mocker, bandcamp_client, raw_item_factory
):
    item = raw_item_factory(item_id=1, sale_item_type="a", sale_item_id=1)
    bandcamp_client.request = mocker.Mock(
        side_effect=[
            _page([item], redownload_urls={"a1": "https://example.com/dl"}),
            _page([]),
        ]
    )

    bandcamp_client.load_purchases()

    assert len(bandcamp_client.purchases) == 1
    assert bandcamp_client.purchases[0].download_url == "https://example.com/dl"


def test_stop_when_halts_pagination_after_matching_item(mocker, bandcamp_client, raw_item_factory):
    matching_item = raw_item_factory(item_id=1, sale_item_type="a", sale_item_id=1)
    later_item = raw_item_factory(item_id=2, sale_item_type="a", sale_item_id=2)
    bandcamp_client.request = mocker.Mock(
        return_value=_page(
            [matching_item, later_item],
            redownload_urls={"a1": "https://example.com/1", "a2": "https://example.com/2"},
        )
    )

    bandcamp_client.load_purchases(stop_when=lambda item: item.item_id == 1)

    assert [item.item_id for item in bandcamp_client.collection_items] == [1]
    assert bandcamp_client.purchases == []
    bandcamp_client.request.assert_called_once()


def test_pagination_advances_token_across_pages(mocker, bandcamp_client, raw_item_factory):
    item_page_1 = raw_item_factory(
        item_id=1, sale_item_type="a", sale_item_id=1, token="page1-token"
    )
    item_page_2 = raw_item_factory(
        item_id=2, sale_item_type="a", sale_item_id=2, token="page2-token"
    )
    bandcamp_client.request = mocker.Mock(
        side_effect=[
            _page([item_page_1], redownload_urls={"a1": "https://example.com/1"}),
            _page([item_page_2], redownload_urls={"a2": "https://example.com/2"}),
            _page([]),
        ]
    )

    bandcamp_client.load_purchases()

    assert len(bandcamp_client.purchases) == 2
    assert bandcamp_client.request.call_count == 3
    second_call_data = bandcamp_client.request.call_args_list[1].kwargs["json_data"]
    assert second_call_data["older_than_token"] == "page1-token"


def test_deduplicates_purchases_sharing_band_and_title(mocker, bandcamp_client, raw_item_factory):
    item_a = raw_item_factory(
        item_id=1, sale_item_type="a", sale_item_id=1, band_name="Band", item_title="Album"
    )
    item_b = raw_item_factory(
        item_id=2, sale_item_type="a", sale_item_id=2, band_name="Band", item_title="Album"
    )
    bandcamp_client.request = mocker.Mock(
        side_effect=[
            _page(
                [item_a, item_b],
                redownload_urls={"a1": "https://example.com/1", "a2": "https://example.com/2"},
            ),
            _page([]),
        ]
    )

    bandcamp_client.load_purchases()

    assert [item.folder_suffix for item in bandcamp_client.purchases] == [" [1]", " [2]"]
