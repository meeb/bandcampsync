import json
from html import escape
from pathlib import Path
from unittest.mock import Mock

import pytest
from bs4 import BeautifulSoup

from bandcampsync.bandcamp import (
    Bandcamp,
    BandcampDownloadUnavailable,
    BandcampError,
    BandcampItem,
)
from bandcampsync.config import BROWSER_PROFILE_WAIT, BROWSER_PROFILES


def _load_payload(name):
    fixture_path = Path(__file__).resolve().parent / "data" / name
    return json.loads(fixture_path.read_text(encoding="utf-8", errors="ignore"))


def _create_bandcamp():
    bandcamp = Bandcamp("identity=test")
    bandcamp.is_authenticated = True
    bandcamp.user_id = 1
    return bandcamp


def _download_key(item):
    return f"{item['sale_item_type']}{item['sale_item_id']}"


@pytest.fixture
def bandcamp():
    return _create_bandcamp()


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


# Tests if an item is a physical purchase (though may also include a digital component).
def test_is_physical_purchase_true(physical_item):
    assert BandcampItem(physical_item).is_physical_purchase() is True


# Tests if an item is _not_ a physical purchase (though doesn't necessarily include a digital component).
def test_is_physical_purchase_false(digital_item):
    assert BandcampItem(digital_item).is_physical_purchase() is False


# Tests if a download URL can be retrieved for a digital purchase.
def test_resolve_download_url_digital(bandcamp, digital_payload, digital_item):
    item = BandcampItem(digital_item)
    download_url = bandcamp._resolve_download_url(
        item,
        digital_payload["redownload_urls"],
    )
    expected_key = _download_key(digital_item)
    assert download_url == digital_payload["redownload_urls"][expected_key]


# Tests that no download URL can be retrieved for a physical-only purchase.
def test_resolve_download_url_physical(bandcamp, physical_payload, physical_item):
    item = BandcampItem(physical_item)
    download_url = bandcamp._resolve_download_url(
        item,
        physical_payload["redownload_urls"],
    )
    assert download_url is None


def test_load_purchases_can_stop_at_physical_only_item(
    bandcamp,
    physical_payload,
    physical_item,
):
    bandcamp._request = Mock(return_value=physical_payload)

    bandcamp.load_purchases(
        stop_when=lambda item: (
            item.band_name == physical_item["band_name"]
            and item.item_title == physical_item["item_title"]
        )
    )

    assert [item.item_id for item in bandcamp.collection_items] == [
        physical_item["item_id"]
    ]
    assert bandcamp.purchases == []


def test_get_download_file_url_missing_downloads_is_unavailable(bandcamp):
    item = BandcampItem(
        {
            "band_name": "Scuba",
            "item_title": "Hardcore Heaven II",
            "item_id": 123,
            "download_url": "https://bandcamp.com/download/test",
        }
    )
    bandcamp._request = Mock()
    bandcamp._extract_pagedata_from_soup = Mock(
        return_value={"digital_items": [{"item_id": 123}]}
    )

    with pytest.raises(BandcampDownloadUnavailable):
        bandcamp.get_download_file_url(item)


CHALLENGE_HTML = (
    "<!DOCTYPE html><html><head><title>Client Challenge</title></head>"
    "<body><script src='/_fs-ch-abc/script.js'></script></body></html>"
)
HOME_HTML = (
    '<html><div id="HomepageApp" data-blob="'
    + escape(
        json.dumps(
            {
                "pageContext": {
                    "identity": {"fanId": 1, "isFanVerified": True},
                }
            }
        )
    )
    + '"></div></html>'
)


class _Response:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class _FakeCookieJar:
    jar = ()

    def set(self, *args, **kwargs):
        return None


def _install_fake_session(monkeypatch, responses):
    created = []

    class FakeSession:
        def __init__(self, impersonate=None):
            self.impersonate = impersonate
            self.cookies = _FakeCookieJar()
            created.append(impersonate)

        def request(self, *args, **kwargs):
            return responses.pop(0)

    monkeypatch.setattr("bandcampsync.bandcamp.requests.Session", FakeSession)
    monkeypatch.setattr("bandcampsync.bandcamp.sleep", lambda seconds: None)
    return created


def test_verify_authentication_retries_after_client_challenge(monkeypatch):
    created = _install_fake_session(
        monkeypatch,
        [_Response(CHALLENGE_HTML), _Response(HOME_HTML)],
    )
    bandcamp = Bandcamp("identity=test")

    assert bandcamp.verify_authentication() is True
    assert bandcamp.user_id == 1
    assert bandcamp.user_verified is True
    assert created == list(BROWSER_PROFILES[:2])
    assert bandcamp.browser_profile == BROWSER_PROFILES[1]


def test_verify_authentication_reports_client_challenge(monkeypatch):
    _install_fake_session(
        monkeypatch,
        [_Response(CHALLENGE_HTML) for _ in BROWSER_PROFILES],
    )
    bandcamp = Bandcamp("identity=test")

    with pytest.raises(BandcampError, match="client challenge"):
        bandcamp.verify_authentication()


def test_impersonate_replaces_fallback_profiles(monkeypatch):
    created = _install_fake_session(monkeypatch, [_Response(CHALLENGE_HTML)])
    bandcamp = Bandcamp("identity=test", impersonate=" safari260 ")

    with pytest.raises(BandcampError, match="client challenge"):
        bandcamp.verify_authentication()
    assert bandcamp.browser_profile == "safari260"
    assert created == ["safari260"]


@pytest.mark.parametrize("impersonate", [None, "", "   "])
def test_missing_impersonate_uses_configured_profiles(impersonate):
    bandcamp = Bandcamp("identity=test", impersonate=impersonate)

    assert bandcamp.browser_profile == BROWSER_PROFILES[0]
    assert bandcamp.browser_profiles == tuple(BROWSER_PROFILES)


def test_no_profiles_available_is_reported(monkeypatch):
    monkeypatch.setattr("bandcampsync.bandcamp.BROWSER_PROFILES", ())

    with pytest.raises(BandcampError, match="No browser profiles"):
        Bandcamp("identity=test")
    assert Bandcamp("identity=test", impersonate="safari260").browser_profiles == (
        "safari260",
    )


def test_blocked_request_reports_url_and_keeps_current_profile(monkeypatch):
    _install_fake_session(
        monkeypatch,
        [_Response(CHALLENGE_HTML) for _ in BROWSER_PROFILES],
    )
    waits = []
    monkeypatch.setattr("bandcampsync.bandcamp.sleep", waits.append)
    bandcamp = Bandcamp("identity=test")

    with pytest.raises(BandcampError) as error:
        bandcamp._request("get", "https://bandcamp.com/page")

    assert "https://bandcamp.com/page" in str(error.value)
    for profile in BROWSER_PROFILES:
        assert profile in str(error.value)
    assert waits == [BROWSER_PROFILE_WAIT] * (len(BROWSER_PROFILES) - 1)
    assert bandcamp.browser_profile == BROWSER_PROFILES[0]


def test_working_profile_is_kept_for_later_requests(monkeypatch):
    created = _install_fake_session(
        monkeypatch,
        [_Response(CHALLENGE_HTML), _Response("first"), _Response("second")],
    )
    waits = []
    monkeypatch.setattr("bandcampsync.bandcamp.sleep", waits.append)
    bandcamp = Bandcamp("identity=test")

    assert bandcamp._request("get", "https://bandcamp.com/", as_raw=True) == "first"
    assert bandcamp._request("get", "https://bandcamp.com/", as_raw=True) == "second"
    assert created == list(BROWSER_PROFILES[:2])
    assert len(waits) == 1


def test_new_profile_gets_cookies_except_challenge_state():
    bandcamp = Bandcamp("identity=test")
    current = bandcamp._session_for(BROWSER_PROFILES[0])
    current.cookies.set("client_id", "abc", domain="bandcamp.com")
    current.cookies.set("_fs_ch_st_abc", "state", domain="bandcamp.com")

    session = bandcamp._session_for(BROWSER_PROFILES[1])

    names = {cookie.name for cookie in session.cookies.jar}
    assert names == {"identity", "client_id"}


def test_item_missing_attribute_uses_getattr_default():
    item = BandcampItem({})

    assert getattr(item, "purchased", "default") == "default"
    with pytest.raises(AttributeError):
        item.purchased


def test_identity_cookie_is_not_logged(caplog):
    with caplog.at_level("DEBUG"):
        Bandcamp("identity=secret-identity-value")

    assert "secret" not in caplog.text


def test_missing_page_data_error_is_a_readable_message():
    soup = BeautifulSoup('<div id="pagedata"></div>', "html.parser")

    with pytest.raises(BandcampError) as error:
        Bandcamp._extract_pagedata_from_soup(soup)

    assert str(error.value) == (
        "Failed to extract page data, check your cookies are from an "
        "authenticated session"
    )


def test_null_downloads_is_unavailable(bandcamp):
    item = BandcampItem(
        {
            "item_id": 1,
            "band_name": "Band",
            "item_title": "Album",
            "download_url": "url",
        }
    )
    blob = escape(json.dumps({"digital_items": [{"item_id": 1, "downloads": None}]}))
    soup = BeautifulSoup(f'<div id="pagedata" data-blob="{blob}"></div>', "html.parser")
    bandcamp._request = Mock(return_value=soup)

    with pytest.raises(BandcampDownloadUnavailable):
        bandcamp.get_download_file_url(item)


def test_pagination_stops_when_the_token_does_not_change():
    bandcamp = _create_bandcamp()
    page = {
        "items": [
            {
                "item_id": 1,
                "band_name": "Band",
                "item_title": "Album",
                "sale_item_type": "a",
                "sale_item_id": 1,
            }
        ],
        "redownload_urls": {"a1": "https://bandcamp.test/1"},
    }
    bandcamp._request = Mock(return_value=page)

    assert bandcamp.load_purchases() is True

    assert bandcamp._request.call_count == 1
    assert len(bandcamp.purchases) == 1


@pytest.mark.parametrize("fan_id", [None, 0])
def test_missing_fan_id_warns_and_stops_before_loading(monkeypatch, caplog, fan_id):
    home = (
        '<html><div id="HomepageApp" data-blob="'
        + escape(
            json.dumps(
                {"pageContext": {"identity": {"fanId": fan_id, "isFanVerified": False}}}
            )
        )
        + '"></div></html>'
    )
    _install_fake_session(monkeypatch, [_Response(home)])
    bandcamp = Bandcamp("identity=test")

    assert bandcamp.verify_authentication() is True

    assert bandcamp.is_authenticated is False
    assert "did not return an account" in caplog.text
    with pytest.raises(BandcampError, match="check your cookies"):
        bandcamp.load_purchases()


def test_load_purchases_groups_names_matching_after_cleaning():
    bandcamp = _create_bandcamp()
    items = [
        {
            "item_id": item_id,
            "band_name": "Band",
            "item_title": title,
            "token": f"token-{item_id}",
            "sale_item_type": "a",
            "sale_item_id": item_id,
        }
        for item_id, title in ((1, "What?"), (2, "WHAT"), (3, "Other"))
    ]
    pages = [
        {
            "items": items,
            "redownload_urls": {
                f"a{i}": f"https://bandcamp.test/{i}" for i in (1, 2, 3)
            },
        },
        {"items": [], "redownload_urls": {}},
    ]
    bandcamp._request = Mock(side_effect=pages)

    bandcamp.load_purchases()

    suffixes = {item.item_id: item.folder_suffix for item in bandcamp.purchases}
    assert suffixes == {1: " [1]", 2: " [2]", 3: ""}
