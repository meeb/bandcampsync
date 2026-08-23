"""Tests for bandcampsync.domain.collection.download_purchase.download_attempt."""

import importlib
from unittest.mock import Mock, patch

import pytest

from bandcampsync.domain.collection.download_purchase.download_attempt import (
    PlacementRetryNeeded,
    attempt_download,
)
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome

# importlib avoids the download_purchase package's __init__.py re-export of the
# download_purchase() function shadowing the normal `import ... as x` attribute chain.
download_attempt_module = importlib.import_module(
    "bandcampsync.domain.collection.download_purchase.download_attempt"
)


def _ctx(tmp_path):
    bandcamp = Mock()
    bandcamp.get_download_file_url.return_value = "https://example.com/initial"
    bandcamp.check_download_stat.return_value = "https://example.com/resolved"
    bandcamp.fetch_purchase_file.return_value = "audio/flac"
    return Mock(bandcamp=bandcamp, temp_dir_root=tmp_path)


def _purchase():
    return Mock(band_name="Band", item_title="Item", item_id=1)


def test_marks_downloaded_and_returns_true_on_successful_placement(tmp_path):
    ctx = _ctx(tmp_path)
    record_error = Mock()

    with (
        patch.object(
            download_attempt_module, "place_downloaded_file", return_value=PlacementOutcome.PLACED
        ),
        patch.object(download_attempt_module, "mark_purchase_downloaded") as mock_mark,
    ):
        result = attempt_download(
            _purchase(), ctx, "flac", tmp_path / "band" / "item", record_error
        )

    assert result.downloaded is True
    mock_mark.assert_called_once()


def test_raises_placement_retry_needed_on_retry_attempt_outcome(tmp_path):
    ctx = _ctx(tmp_path)

    with (
        patch.object(
            download_attempt_module,
            "place_downloaded_file",
            return_value=PlacementOutcome.RETRY_ATTEMPT,
        ),
        patch.object(download_attempt_module, "mark_purchase_downloaded") as mock_mark,
        pytest.raises(PlacementRetryNeeded),
    ):
        attempt_download(_purchase(), ctx, "flac", tmp_path / "band" / "item", Mock())

    mock_mark.assert_not_called()


def test_returns_false_without_marking_on_unrecognized_content(tmp_path):
    ctx = _ctx(tmp_path)

    with (
        patch.object(
            download_attempt_module,
            "place_downloaded_file",
            return_value=PlacementOutcome.UNRECOGNIZED_CONTENT,
        ),
        patch.object(download_attempt_module, "mark_purchase_downloaded") as mock_mark,
    ):
        result = attempt_download(_purchase(), ctx, "flac", tmp_path / "band" / "item", Mock())

    assert result.downloaded is False
    mock_mark.assert_not_called()


def test_resolves_download_url_before_fetching(tmp_path):
    ctx = _ctx(tmp_path)
    purchase = _purchase()

    with (
        patch.object(
            download_attempt_module, "place_downloaded_file", return_value=PlacementOutcome.PLACED
        ),
        patch.object(download_attempt_module, "mark_purchase_downloaded"),
    ):
        attempt_download(purchase, ctx, "flac", tmp_path / "band" / "item", Mock())

    ctx.bandcamp.get_download_file_url.assert_called_once_with(purchase, encoding="flac")
    ctx.bandcamp.check_download_stat.assert_called_once_with(
        purchase, "https://example.com/initial"
    )
    ctx.bandcamp.fetch_purchase_file.assert_called_once()
    assert ctx.bandcamp.fetch_purchase_file.call_args[0][0] == "https://example.com/resolved"
