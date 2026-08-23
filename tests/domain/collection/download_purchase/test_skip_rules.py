"""Tests for bandcampsync.domain.collection.download_purchase.skip_rules."""

from pathlib import Path
from unittest.mock import Mock

from bandcampsync.domain.collection.download_purchase.skip_rules import find_skip_reason


def _ctx(**overrides):
    defaults = {
        "skip_hidden": False,
        "ignores": Mock(is_ignored=Mock(return_value=False)),
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

    result = find_skip_reason(purchase, ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False
    assert result.show_id_file_warning is False


def test_does_not_skip_hidden_items_when_skip_hidden_disabled():
    ctx = _ctx(skip_hidden=False)
    purchase = _purchase(hidden=True)

    assert find_skip_reason(purchase, ctx, Path("/media/band/item")) is None


def test_skips_ignored_items_and_carries_id_file_warning():
    ctx = _ctx(
        ignores=Mock(is_ignored=Mock(return_value=True)),
        local_media=Mock(is_locally_downloaded=Mock(return_value=True)),
    )

    result = find_skip_reason(_purchase(), ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False
    assert result.show_id_file_warning is True


def test_skips_preorders():
    ctx = _ctx()
    purchase = _purchase(is_preorder=True)

    result = find_skip_reason(purchase, ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False


def test_skips_already_locally_downloaded_items():
    ctx = _ctx(local_media=Mock(is_locally_downloaded=Mock(return_value=True)))

    result = find_skip_reason(_purchase(), ctx, Path("/media/band/item"))

    assert result is not None
    assert result.downloaded is False
    assert result.show_id_file_warning is False


def test_returns_none_when_nothing_applies():
    ctx = _ctx()

    assert find_skip_reason(_purchase(), ctx, Path("/media/band/item")) is None
