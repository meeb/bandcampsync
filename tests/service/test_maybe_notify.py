"""Tests for bandcampsync.service.maybe_notify.

Uses importlib to get the real module object rather than
`import bandcampsync.service.maybe_notify` - that (and even
`from bandcampsync.service import maybe_notify`) resolves to the *function*
maybe_notify, not the module, because service/__init__.py re-exports it under
the same name, which shadows the submodule attribute on the package. See
home_server/service/__init__.py's docstring for the same gotcha.
"""

import importlib
from unittest.mock import patch

from bandcampsync.service.maybe_notify import maybe_notify

_module = importlib.import_module("bandcampsync.service.maybe_notify")


def test_dry_run_skips_notify_even_with_new_items():
    with patch.object(_module, "NotifyURL") as mock_notify_cls:
        maybe_notify(dry_run=True, new_items_downloaded=True, notify_url="http://example.com")

    mock_notify_cls.assert_not_called()


def test_no_new_items_skips_notify():
    with patch.object(_module, "NotifyURL") as mock_notify_cls:
        maybe_notify(dry_run=False, new_items_downloaded=False, notify_url="http://example.com")

    mock_notify_cls.assert_not_called()


def test_no_notify_url_skips_notify():
    with patch.object(_module, "NotifyURL") as mock_notify_cls:
        maybe_notify(dry_run=False, new_items_downloaded=True, notify_url=None)

    mock_notify_cls.assert_not_called()


def test_fires_notify_when_all_conditions_met():
    with patch.object(_module, "NotifyURL") as mock_notify_cls:
        maybe_notify(dry_run=False, new_items_downloaded=True, notify_url="http://example.com")

    mock_notify_cls.assert_called_once_with("http://example.com")
    mock_notify_cls.return_value.notify.assert_called_once()
