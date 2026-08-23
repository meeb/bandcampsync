"""Tests for bandcampsync.domain.collection.download_purchase.download_purchase."""

import importlib
from unittest.mock import Mock, patch

from bandcampsync.domain.bandcamp import (
    BandcampDownloadExpired,
    BandcampDownloadUnavailable,
    BandcampError,
)
from bandcampsync.domain.collection.download_purchase.context import PurchaseDownloadResult
from bandcampsync.domain.collection.download_purchase.download_attempt import PlacementRetryNeeded
from bandcampsync.domain.collection.download_purchase.download_purchase import download_purchase
from bandcampsync.domain.file_transfer import TransferBadStatusCode

# importlib avoids the download_purchase package's __init__.py re-export of the
# download_purchase() function shadowing the normal `import ... as x` attribute chain.
download_purchase_module = importlib.import_module(
    "bandcampsync.domain.collection.download_purchase.download_purchase"
)


def _ctx(**overrides):
    local_media = Mock()
    local_media.get_path_for_purchase.return_value = "/media/band/item"
    defaults = {
        "local_media": local_media,
        "media_format": "flac",
        "dry_run": False,
        "max_retries": 3,
        "retry_wait": 0,
    }
    defaults.update(overrides)
    return Mock(**defaults)


def _purchase():
    return Mock(band_name="Band", item_title="Item", item_id=1)


def test_returns_skip_result_without_attempting_download():
    skip_result = PurchaseDownloadResult(downloaded=False, show_id_file_warning=True)
    ctx = _ctx()

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=skip_result),
        patch.object(download_purchase_module, "attempt_download") as mock_attempt,
    ):
        result = download_purchase(_purchase(), ctx, Mock())

    assert result is skip_result
    mock_attempt.assert_not_called()


def test_dry_run_does_not_attempt_download():
    ctx = _ctx(dry_run=True)

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(download_purchase_module, "attempt_download") as mock_attempt,
    ):
        result = download_purchase(_purchase(), ctx, Mock())

    assert result.downloaded is False
    mock_attempt.assert_not_called()


def test_successful_attempt_is_returned_directly():
    ctx = _ctx()
    success = PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(download_purchase_module, "attempt_download", return_value=success),
    ):
        result = download_purchase(_purchase(), ctx, Mock())

    assert result is success


def test_placement_retry_needed_retries_without_sleeping():
    ctx = _ctx()
    success = PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(
            download_purchase_module,
            "attempt_download",
            side_effect=[PlacementRetryNeeded(), success],
        ) as mock_attempt,
    ):
        result = download_purchase(_purchase(), ctx, Mock())

    assert result is success
    assert mock_attempt.call_count == 2


def test_download_unavailable_skips_without_recording_error():
    ctx = _ctx()
    record_error = Mock()

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(
            download_purchase_module,
            "attempt_download",
            side_effect=BandcampDownloadUnavailable("gone"),
        ),
    ):
        result = download_purchase(_purchase(), ctx, record_error)

    assert result.downloaded is False
    record_error.assert_not_called()


def test_download_expired_records_error_and_does_not_retry():
    ctx = _ctx()
    record_error = Mock()

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(
            download_purchase_module,
            "attempt_download",
            side_effect=BandcampDownloadExpired("expired"),
        ) as mock_attempt,
    ):
        result = download_purchase(_purchase(), ctx, record_error)

    assert result.downloaded is False
    record_error.assert_called_once()
    assert mock_attempt.call_count == 1


def test_bandcamp_error_retries_then_records_error_after_exhausting_attempts():
    ctx = _ctx(max_retries=2, retry_wait=0)
    record_error = Mock()

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(
            download_purchase_module, "attempt_download", side_effect=BandcampError("boom")
        ) as mock_attempt,
        patch.object(download_purchase_module.time, "sleep"),
    ):
        result = download_purchase(_purchase(), ctx, record_error)

    assert result.downloaded is False
    assert mock_attempt.call_count == 2
    record_error.assert_called_once()


def test_bad_status_code_is_retried_like_a_bandcamp_error():
    ctx = _ctx(max_retries=2, retry_wait=0)
    record_error = Mock()

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(
            download_purchase_module,
            "attempt_download",
            side_effect=[
                TransferBadStatusCode("502"),
                PurchaseDownloadResult(downloaded=True, show_id_file_warning=False),
            ],
        ),
        patch.object(download_purchase_module.time, "sleep"),
    ):
        result = download_purchase(_purchase(), ctx, record_error)

    assert result.downloaded is True
    record_error.assert_not_called()


def test_encoding_override_takes_precedence_over_context_media_format():
    ctx = _ctx(media_format="flac")
    success = PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)

    with (
        patch.object(download_purchase_module, "find_skip_reason", return_value=None),
        patch.object(
            download_purchase_module, "attempt_download", return_value=success
        ) as mock_attempt,
    ):
        download_purchase(_purchase(), ctx, Mock(), encoding="mp3-320")

    assert mock_attempt.call_args[0][2] == "mp3-320"
