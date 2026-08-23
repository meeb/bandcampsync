"""Tests for bandcampsync.domain.collection.download_purchase.skip_rules."""

import importlib
from pathlib import Path
from unittest.mock import Mock, patch

from bandcampsync.domain.collection.download_purchase.skip_rules import find_skip_reason

# importlib avoids the download_purchase package's __init__.py re-export of the
# download_purchase() function shadowing the normal `import ... as x` attribute chain.
skip_rules_module = importlib.import_module(
    "bandcampsync.domain.collection.download_purchase.skip_rules"
)


def _ctx(**overrides):
    defaults = {
        "skip_hidden": False,
        "ignore_rules": Mock(),
        "local_media": Mock(is_locally_downloaded=Mock(return_value=False)),
    }
    defaults.update(overrides)
    return Mock(**defaults)


def _purchase(**overrides):
    defaults = {"hidden": False, "is_preorder": False}
    defaults.update(overrides)
    return Mock(**defaults)


def test_skips_hidden_items_when_skip_hidden_enabled():
    ctx = _ctx(skip_hidden=True)
    purchase = _purchase(hidden=True)

    with patch.object(skip_rules_module, "is_ignored", return_value=False):
        result = find_skip_reason(purchase, ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False
    assert result.show_id_file_warning is False


def test_does_not_skip_hidden_items_when_skip_hidden_disabled():
    ctx = _ctx(skip_hidden=False)
    purchase = _purchase(hidden=True)

    with patch.object(skip_rules_module, "is_ignored", return_value=False):
        assert find_skip_reason(purchase, ctx, Path("/media/band/item")) is None


def test_skips_ignored_items_and_carries_id_file_warning():
    ctx = _ctx(local_media=Mock(is_locally_downloaded=Mock(return_value=True)))

    with patch.object(skip_rules_module, "is_ignored", return_value=True):
        result = find_skip_reason(_purchase(), ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False
    assert result.show_id_file_warning is True


def test_skips_preorders():
    ctx = _ctx()
    purchase = _purchase(is_preorder=True)

    with patch.object(skip_rules_module, "is_ignored", return_value=False):
        result = find_skip_reason(purchase, ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False


def test_skips_already_locally_downloaded_items():
    ctx = _ctx(local_media=Mock(is_locally_downloaded=Mock(return_value=True)))

    with patch.object(skip_rules_module, "is_ignored", return_value=False):
        result = find_skip_reason(_purchase(), ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False
    assert result.show_id_file_warning is False


def test_returns_none_when_nothing_applies():
    ctx = _ctx()

    with patch.object(skip_rules_module, "is_ignored", return_value=False):
        assert find_skip_reason(_purchase(), ctx, Path("/media/band/item")) is None
