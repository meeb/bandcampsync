"""Tests for bandcampsync.service.do_sync.

Uses importlib to get the real module object - see test_maybe_notify.py's
docstring for why a plain import doesn't work here.
"""

import importlib
from unittest.mock import Mock, patch

from bandcampsync.service.do_sync import do_sync

_module = importlib.import_module("bandcampsync.service.do_sync")


def test_delegates_to_sync_collection_and_returns_true():
    options = Mock()

    with patch.object(_module, "sync_collection") as mock_sync_collection:
        result = do_sync(options)

    mock_sync_collection.assert_called_once_with(options)
    assert result is True
