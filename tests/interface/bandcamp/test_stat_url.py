"""Tests for bandcampsync.interface.bandcamp.stat_url."""

from bandcampsync.interface.bandcamp.stat_url import parse_js_stat_url


def test_returns_original_url_on_ok_result():
    body = "var _statDL_result = { result: 'ok'};"
    assert parse_js_stat_url(body, "https://example.com/original") == "https://example.com/original"


def test_strips_surrounding_whitespace_before_checking_ok_result():
    body = "  var _statDL_result = { result: 'ok'};  \n"
    assert parse_js_stat_url(body, "https://example.com/original") == "https://example.com/original"


def test_extracts_updated_download_url_from_key_value_pairs():
    body = '{"foo":"bar","download_url":"https://example.com/updated"}'
    assert parse_js_stat_url(body, "https://example.com/original") == "https://example.com/updated"


def test_falls_back_to_original_url_when_no_download_url_key_present():
    body = '{"foo":"bar","baz":"qux"}'
    assert parse_js_stat_url(body, "https://example.com/original") == "https://example.com/original"


def test_falls_back_to_original_url_on_unparseable_body():
    assert parse_js_stat_url("not json or js at all", "https://example.com/original") == (
        "https://example.com/original"
    )
