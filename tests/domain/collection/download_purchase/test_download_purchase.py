"""Tests for bandcampsync.domain.collection.download_purchase.download_purchase."""

import importlib

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


def _ctx(mocker, purchase_download_context_factory, **overrides):
    local_media = mocker.Mock()
    local_media.get_path_for_purchase.return_value = "/media/band/item"
    overrides.setdefault("local_media", local_media)
    return purchase_download_context_factory(**overrides)


def test_returns_skip_result_without_attempting_download(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    skip_result = PurchaseDownloadResult(downloaded=False, show_id_file_warning=True)
    ctx = _ctx(mocker, purchase_download_context_factory)
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=skip_result)
    mock_attempt = mocker.patch.object(download_purchase_module, "attempt_download")

    result = download_purchase(bandcamp_item_factory(), ctx, mocker.Mock())

    assert result is skip_result
    mock_attempt.assert_not_called()


def test_dry_run_does_not_attempt_download(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory, dry_run=True)
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mock_attempt = mocker.patch.object(download_purchase_module, "attempt_download")

    result = download_purchase(bandcamp_item_factory(), ctx, mocker.Mock())

    assert result.downloaded is False
    mock_attempt.assert_not_called()


def test_successful_attempt_is_returned_directly(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory)
    success = PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mocker.patch.object(download_purchase_module, "attempt_download", return_value=success)

    result = download_purchase(bandcamp_item_factory(), ctx, mocker.Mock())

    assert result is success


def test_placement_retry_needed_retries_without_sleeping(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory)
    success = PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mock_attempt = mocker.patch.object(
        download_purchase_module,
        "attempt_download",
        side_effect=[PlacementRetryNeeded(), success],
    )

    result = download_purchase(bandcamp_item_factory(), ctx, mocker.Mock())

    assert result is success
    assert mock_attempt.call_count == 2


def test_download_unavailable_skips_without_recording_error(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory)
    record_error = mocker.Mock()
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mocker.patch.object(
        download_purchase_module,
        "attempt_download",
        side_effect=BandcampDownloadUnavailable("gone"),
    )

    result = download_purchase(bandcamp_item_factory(), ctx, record_error)

    assert result.downloaded is False
    record_error.assert_not_called()


def test_download_expired_records_error_and_does_not_retry(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory)
    record_error = mocker.Mock()
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mock_attempt = mocker.patch.object(
        download_purchase_module,
        "attempt_download",
        side_effect=BandcampDownloadExpired("expired"),
    )

    result = download_purchase(bandcamp_item_factory(), ctx, record_error)

    assert result.downloaded is False
    record_error.assert_called_once()
    assert mock_attempt.call_count == 1


def test_bandcamp_error_retries_then_records_error_after_exhausting_attempts(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory, max_retries=2, retry_wait=0)
    record_error = mocker.Mock()
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mock_attempt = mocker.patch.object(
        download_purchase_module, "attempt_download", side_effect=BandcampError("boom")
    )
    mocker.patch.object(download_purchase_module.time, "sleep")

    result = download_purchase(bandcamp_item_factory(), ctx, record_error)

    assert result.downloaded is False
    assert mock_attempt.call_count == 2
    record_error.assert_called_once()


def test_bad_status_code_is_retried_like_a_bandcamp_error(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory, max_retries=2, retry_wait=0)
    record_error = mocker.Mock()
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mocker.patch.object(
        download_purchase_module,
        "attempt_download",
        side_effect=[
            TransferBadStatusCode("502"),
            PurchaseDownloadResult(downloaded=True, show_id_file_warning=False),
        ],
    )
    mocker.patch.object(download_purchase_module.time, "sleep")

    result = download_purchase(bandcamp_item_factory(), ctx, record_error)

    assert result.downloaded is True
    record_error.assert_not_called()


def test_encoding_override_takes_precedence_over_context_media_format(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = _ctx(mocker, purchase_download_context_factory, media_format="flac")
    success = PurchaseDownloadResult(downloaded=True, show_id_file_warning=False)
    mocker.patch.object(download_purchase_module, "find_skip_reason", return_value=None)
    mock_attempt = mocker.patch.object(
        download_purchase_module, "attempt_download", return_value=success
    )

    download_purchase(bandcamp_item_factory(), ctx, mocker.Mock(), encoding="mp3-320")

    assert mock_attempt.call_args[0][2] == "mp3-320"
