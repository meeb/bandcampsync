"""Tests for bandcampsync.domain.collection.download_purchase.place_single_track."""

import importlib
from unittest.mock import Mock, patch

from bandcampsync.domain.collection.download_purchase.place_single_track import (
    place_single_track,
)
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome

# importlib avoids the download_purchase package's __init__.py re-export of the
# download_purchase() function shadowing the normal `import ... as x` attribute chain.
place_single_track_module = importlib.import_module(
    "bandcampsync.domain.collection.download_purchase.place_single_track"
)


def _ctx(tmp_path):
    local_media = Mock()
    local_media.clean_format.return_value = "flac"
    local_media.get_path_for_file.side_effect = lambda local_path, name: local_path / name
    return Mock(local_media=local_media)


def test_uses_url_hints_slug_when_present(tmp_path):
    ctx = _ctx(tmp_path)
    purchase = Mock(item_title="Fallback Title", url_hints={"slug": "hinted-slug"})
    local_path = tmp_path / "band" / "item"

    with patch.object(place_single_track_module, "copy_file") as mock_copy:
        outcome = place_single_track(purchase, ctx, tmp_path / "temp", "flac", local_path, Mock())

    assert outcome is PlacementOutcome.PLACED
    mock_copy.assert_called_once_with(tmp_path / "temp", local_path / "hinted-slug.flac")


def test_falls_back_to_item_title_without_url_hints(tmp_path):
    ctx = _ctx(tmp_path)
    purchase = Mock(item_title="Item Title", url_hints=None)
    local_path = tmp_path / "band" / "item"

    with patch.object(place_single_track_module, "copy_file") as mock_copy:
        outcome = place_single_track(purchase, ctx, tmp_path / "temp", "flac", local_path, Mock())

    assert outcome is PlacementOutcome.PLACED
    mock_copy.assert_called_once_with(tmp_path / "temp", local_path / "Item Title.flac")


def test_mkdir_failure_records_error_and_requests_retry(tmp_path):
    ctx = _ctx(tmp_path)
    purchase = Mock(item_title="Item", url_hints=None)
    record_error = Mock()
    # A file in place of the target directory makes mkdir fail.
    blocking_file = tmp_path / "blocked"
    blocking_file.write_text("not a directory")

    with patch.object(place_single_track_module, "copy_file") as mock_copy:
        outcome = place_single_track(
            purchase, ctx, tmp_path / "temp", "flac", blocking_file / "item", record_error
        )

    assert outcome is PlacementOutcome.RETRY_ATTEMPT
    record_error.assert_called_once()
    mock_copy.assert_not_called()


def test_copy_failure_records_error_but_still_reports_placed(tmp_path):
    ctx = _ctx(tmp_path)
    purchase = Mock(item_title="Item", url_hints=None)
    record_error = Mock()
    local_path = tmp_path / "band" / "item"

    with patch.object(place_single_track_module, "copy_file", side_effect=OSError("boom")):
        outcome = place_single_track(
            purchase, ctx, tmp_path / "temp", "flac", local_path, record_error
        )

    assert outcome is PlacementOutcome.PLACED
    record_error.assert_called_once()
    assert "boom" in record_error.call_args[0][0]
