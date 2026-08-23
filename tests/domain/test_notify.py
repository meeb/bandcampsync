"""Tests for bandcampsync.domain.notify.NotifyURL."""

from unittest.mock import Mock, patch

from bandcampsync.domain.notify import NotifyURL


def test_empty_string_is_invalid():
    notify = NotifyURL("")
    assert notify.valid is False


def test_url_only_defaults_to_get():
    notify = NotifyURL("https://example.com/hook")
    assert notify.valid is True
    assert notify.method == "GET"
    assert notify.url == "https://example.com/hook"
    assert notify.headers == {}
    assert notify.body == ""


def test_full_form_parses_method_headers_and_body():
    notify = NotifyURL("post https://example.com/hook a=1,b=2 hello")
    assert notify.valid is True
    assert notify.method == "POST"
    assert notify.url == "https://example.com/hook"
    assert notify.headers == {"a": "1", "b": "2"}
    assert notify.body == "hello"


def test_full_form_treats_dash_as_no_headers_or_body():
    notify = NotifyURL("GET https://example.com/hook - -")
    assert notify.valid is True
    assert notify.headers == {}
    assert notify.body == ""


def test_invalid_method_is_rejected():
    notify = NotifyURL("PUT https://example.com/hook - -")
    assert notify.valid is False


def test_wrong_number_of_parts_is_rejected():
    notify = NotifyURL("GET https://example.com/hook onlyheaders")
    assert notify.valid is False


def test_notify_returns_false_when_invalid():
    notify = NotifyURL("")
    assert notify.notify() is False


def test_notify_get_returns_true_on_2xx():
    notify = NotifyURL("https://example.com/hook")
    with patch("bandcampsync.domain.notify.requests.get", return_value=Mock(status_code=204)):
        assert notify.notify() is True


def test_notify_post_sends_body_and_merges_headers():
    # A single "key=value" header is only parsed when there's a comma to
    # split on - see parse_notify_str()'s "," in headers check - so two
    # headers are used here to exercise that path.
    notify = NotifyURL("post https://example.com/hook a=1,b=2 hello")
    with patch(
        "bandcampsync.domain.notify.requests.post", return_value=Mock(status_code=200)
    ) as mock_post:
        assert notify.notify() is True

    _, kwargs = mock_post.call_args
    assert kwargs["data"] == "hello"
    assert kwargs["headers"]["a"] == "1"
    assert kwargs["headers"]["b"] == "2"
    assert "User-Agent" in kwargs["headers"]


def test_notify_does_not_let_custom_headers_override_user_agent():
    notify = NotifyURL("post https://example.com/hook User-Agent=custom,a=1 hello")
    with patch(
        "bandcampsync.domain.notify.requests.post", return_value=Mock(status_code=200)
    ) as mock_post:
        notify.notify()

    assert mock_post.call_args.kwargs["headers"]["User-Agent"] != "custom"


def test_notify_returns_false_on_non_2xx():
    notify = NotifyURL("https://example.com/hook")
    with patch("bandcampsync.domain.notify.requests.get", return_value=Mock(status_code=500)):
        assert notify.notify() is False
