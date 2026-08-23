"""Tests for bandcampsync.domain.collection.download_purchase.file_placement."""

import importlib
from pathlib import Path

from bandcampsync.domain.collection.download_purchase.file_placement import (
    is_single_track,
    place_downloaded_file,
)
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome

# importlib avoids the download_purchase package's __init__.py re-export of the
# download_purchase() function shadowing the normal `import ... as x` attribute chain.
file_placement_module = importlib.import_module(
    "bandcampsync.domain.collection.download_purchase.file_placement"
)


def test_is_single_track_true_for_track_item_type(track_factory):
    assert is_single_track(track_factory(), "application/zip") is True


def test_is_single_track_true_for_audio_content_type(album_factory):
    assert is_single_track(album_factory(), "audio/flac") is True


def test_is_single_track_true_for_ogg_content_type(album_factory):
    assert is_single_track(album_factory(), "application/ogg") is True


def test_is_single_track_false_otherwise(album_factory):
    assert is_single_track(album_factory(), "application/zip") is False


def test_place_downloaded_file_delegates_zip_archives_to_place_zip_archive(
    mocker, album_factory, purchase_download_context_factory
):
    purchase = album_factory()
    ctx = purchase_download_context_factory()
    record_error = mocker.Mock()
    mocker.patch.object(file_placement_module, "is_zip_archive", return_value=True)
    mock_place_zip = mocker.patch.object(
        file_placement_module, "place_zip_archive", return_value=PlacementOutcome.PLACED
    )

    outcome = place_downloaded_file(
        purchase, ctx, Path("/tmp/f"), "application/zip", "flac", Path("/media"), record_error
    )

    mock_place_zip.assert_called_once_with(ctx, Path("/tmp/f"), Path("/media"), record_error)
    assert outcome is PlacementOutcome.PLACED


def test_place_downloaded_file_delegates_single_tracks_to_place_single_track(
    mocker, track_factory, purchase_download_context_factory
):
    purchase = track_factory()
    ctx = purchase_download_context_factory()
    record_error = mocker.Mock()
    mocker.patch.object(file_placement_module, "is_zip_archive", return_value=False)
    mock_place_single = mocker.patch.object(
        file_placement_module, "place_single_track", return_value=PlacementOutcome.PLACED
    )

    outcome = place_downloaded_file(
        purchase, ctx, Path("/tmp/f"), "audio/flac", "flac", Path("/media"), record_error
    )

    mock_place_single.assert_called_once_with(
        purchase, ctx, Path("/tmp/f"), "flac", Path("/media"), record_error
    )
    assert outcome is PlacementOutcome.PLACED


def test_place_downloaded_file_rejects_unrecognized_content(
    mocker, album_factory, purchase_download_context_factory
):
    purchase = album_factory(band_name="Band", item_title="Item", item_id=1)
    ctx = purchase_download_context_factory()
    record_error = mocker.Mock()
    mocker.patch.object(file_placement_module, "is_zip_archive", return_value=False)

    outcome = place_downloaded_file(
        purchase, ctx, Path("/tmp/f"), "text/html", "flac", Path("/media"), record_error
    )

    assert outcome is PlacementOutcome.UNRECOGNIZED_CONTENT
    record_error.assert_called_once()
