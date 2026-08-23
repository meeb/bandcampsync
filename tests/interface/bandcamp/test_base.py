"""Tests for bandcampsync.interface.bandcamp.base.BandcampClientBase."""

from unittest.mock import Mock

import pytest

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.interface.bandcamp.base import BandcampClientBase


def test_missing_identity_cookie_raises():
    with pytest.raises(BandcampError, match="identity"):
        BandcampClientBase("session=abc")


def test_load_cookies_wraps_parse_failures():
    client = BandcampClientBase("identity=test")

    with pytest.raises(BandcampError, match="Failed to parse cookies string"):
        client.load_cookies(None)


def test_netscape_cookie_format_is_parsed():
    netscape = "\n".join(
        [
            "# Netscape HTTP Cookie File",
            ".bandcamp.com\tTRUE\t/\tTRUE\t1999999999\tidentity\ttestvalue123",
            ".bandcamp.com\tTRUE\t/\tFALSE\t1999999999\tsession\tothervalue",
        ]
    )

    client = BandcampClientBase(netscape)

    assert client.cookies is not None
    assert client.cookies["identity"].value == "testvalue123"
    assert client.cookies["session"].value == "othervalue"


def test_cookies_str_is_semicolon_joined():
    client = BandcampClientBase("identity=abc; session=def")

    cookies_str = client.cookies_str
    assert "identity=abc" in cookies_str
    assert "session=def" in cookies_str
    assert "\r\n" not in cookies_str


def test_refresh_cookes_writes_cookies_str_to_file(tmp_path):
    client = BandcampClientBase("identity=abc")
    target = tmp_path / "cookies.txt"

    client.refresh_cookes(str(target))

    assert "identity=abc" in target.read_text()


def test_plain_cookies_returns_a_name_to_value_mapping():
    client = BandcampClientBase("identity=abc; session=def")

    assert client.plain_cookies() == {"identity": "abc", "session": "def"}


def test_request_returns_parsed_html_by_default():
    client = BandcampClientBase("identity=abc")
    client.session = Mock()
    client.session.request.return_value = Mock(status_code=200, text="<p>hi</p>")

    soup = client._dispatch("get", "https://example.com")

    assert soup.find("p").text == "hi"


def test_dispatch_as_raw_returns_the_response_text():
    client = BandcampClientBase("identity=abc")
    client.session = Mock()
    client.session.request.return_value = Mock(status_code=200, text="raw body")

    assert client._dispatch("get", "https://example.com", as_raw=True) == "raw body"


def test_dispatch_is_json_parses_the_response_body():
    client = BandcampClientBase("identity=abc")
    client.session = Mock()
    client.session.request.return_value = Mock(status_code=200, text='{"a": 1}')

    assert client._dispatch("get", "https://example.com", is_json=True) == {"a": 1}


def test_dispatch_raises_on_non_200_status():
    client = BandcampClientBase("identity=abc")
    client.session = Mock()
    client.session.request.return_value = Mock(status_code=500, text="")

    with pytest.raises(BandcampError, match="500"):
        client._dispatch("get", "https://example.com")


def test_dispatch_wraps_transport_failures():
    client = BandcampClientBase("identity=abc")
    client.session = Mock()
    client.session.request.side_effect = ConnectionError("boom")

    with pytest.raises(BandcampError, match="boom"):
        client._dispatch("get", "https://example.com")


def test_request_authenticates_before_dispatching_when_not_yet_authenticated():
    client = BandcampClientBase("identity=abc")
    client.session = Mock()
    client.session.request.return_value = Mock(status_code=200, text="<p>hi</p>")
    calls = []

    def fake_verify_authentication():
        calls.append("verify_authentication")
        client.is_authenticated = True
        return True

    client.verify_authentication = fake_verify_authentication

    client.request("get", "https://example.com")

    assert calls == ["verify_authentication"]


def test_request_skips_authentication_when_already_authenticated():
    client = BandcampClientBase("identity=abc")
    client.is_authenticated = True
    client.session = Mock()
    client.session.request.return_value = Mock(status_code=200, text="<p>hi</p>")
    client.verify_authentication = Mock(side_effect=AssertionError("should not be called"))

    client.request("get", "https://example.com")

    client.verify_authentication.assert_not_called()


def test_base_verify_authentication_is_an_unimplemented_stub():
    client = BandcampClientBase("identity=abc")

    with pytest.raises(NotImplementedError):
        client.verify_authentication()
