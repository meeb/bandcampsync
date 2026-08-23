"""Tests for bandcampsync.domain.collection.download_purchase.place_zip_archive."""

import importlib

from bandcampsync.domain.collection.download_purchase.place_zip_archive import place_zip_archive
from bandcampsync.domain.collection.download_purchase.placement_outcome import PlacementOutcome

# importlib avoids the download_purchase package's __init__.py re-export of the
# download_purchase() function shadowing the normal `import ... as x` attribute chain.
place_zip_archive_module = importlib.import_module(
    "bandcampsync.domain.collection.download_purchase.place_zip_archive"
)


def _ctx(mocker, purchase_download_context_factory, **overrides):
    local_media = mocker.Mock()
    local_media.get_path_for_file.side_effect = lambda local_path, name: local_path / name
    return purchase_download_context_factory(local_media=local_media, **overrides)


def _fake_extract(*files):
    def extract(decompress_from, decompress_to):
        for name in files:
            (decompress_to / name).write_text("content")
        return True

    return extract


def test_moves_every_extracted_file_to_local_path(
    mocker, purchase_download_context_factory, tmp_path
):
    ctx = _ctx(mocker, purchase_download_context_factory)
    local_path = tmp_path / "band" / "item"
    record_error = mocker.Mock()
    mocker.patch.object(
        place_zip_archive_module,
        "extract_zip_archive",
        side_effect=_fake_extract("track1.flac", "track2.flac"),
    )

    outcome = place_zip_archive(ctx, tmp_path / "download.zip", local_path, record_error)

    assert outcome is PlacementOutcome.PLACED
    record_error.assert_not_called()
    assert sorted(p.name for p in local_path.iterdir()) == ["track1.flac", "track2.flac"]


def test_mkdir_failure_records_error_and_requests_retry(
    mocker, purchase_download_context_factory, tmp_path
):
    ctx = _ctx(mocker, purchase_download_context_factory)
    record_error = mocker.Mock()
    blocking_file = tmp_path / "blocked"
    blocking_file.write_text("not a directory")
    mocker.patch.object(
        place_zip_archive_module, "extract_zip_archive", side_effect=_fake_extract()
    )

    outcome = place_zip_archive(
        ctx, tmp_path / "download.zip", blocking_file / "item", record_error
    )

    assert outcome is PlacementOutcome.RETRY_ATTEMPT
    record_error.assert_called_once()


def test_move_failure_records_error_but_still_reports_placed(
    mocker, purchase_download_context_factory, tmp_path
):
    ctx = _ctx(mocker, purchase_download_context_factory)
    local_path = tmp_path / "band" / "item"
    record_error = mocker.Mock()
    mocker.patch.object(
        place_zip_archive_module,
        "extract_zip_archive",
        side_effect=_fake_extract("track1.flac"),
    )
    mocker.patch.object(place_zip_archive_module, "move_file", side_effect=OSError("boom"))

    outcome = place_zip_archive(ctx, tmp_path / "download.zip", local_path, record_error)

    assert outcome is PlacementOutcome.PLACED
    record_error.assert_called_once()
    assert "boom" in record_error.call_args[0][0]
