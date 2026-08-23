"""Tests for bandcampsync.domain.collection.download_purchase.local_bookkeeping."""

from pathlib import Path

from bandcampsync.domain.collection.download_purchase.local_bookkeeping import (
    mark_purchase_downloaded,
)


def test_adds_to_ignores_when_ignore_file_configured(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = purchase_download_context_factory(
        ign_file_path=Path("/ignores.txt"), ignore_file_writer=mocker.Mock()
    )
    purchase = bandcamp_item_factory()
    record_error = mocker.Mock()

    mark_purchase_downloaded(purchase, ctx, Path("/media/band/item"), record_error)

    ctx.ignore_file_writer.record.assert_called_once_with(
        purchase.item_id, purchase.band_name, purchase.item_title
    )
    ctx.local_media.write_bandcamp_id.assert_not_called()
    record_error.assert_not_called()


def test_writes_bandcamp_id_when_no_ignore_file_configured(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = purchase_download_context_factory(ign_file_path=None, ignore_file_writer=mocker.Mock())
    purchase = bandcamp_item_factory()
    record_error = mocker.Mock()
    local_path = Path("/media/band/item")

    mark_purchase_downloaded(purchase, ctx, local_path, record_error)

    ctx.local_media.write_bandcamp_id.assert_called_once_with(purchase, local_path)
    ctx.ignore_file_writer.record.assert_not_called()
    record_error.assert_not_called()


def test_records_error_when_writing_bandcamp_id_fails(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = purchase_download_context_factory(ign_file_path=None)
    ctx.local_media.write_bandcamp_id.side_effect = OSError("disk full")
    purchase = bandcamp_item_factory(band_name="Band", item_title="Item", item_id=1)
    record_error = mocker.Mock()

    mark_purchase_downloaded(purchase, ctx, Path("/media/band/item"), record_error)

    record_error.assert_called_once()
    assert "disk full" in record_error.call_args[0][0]


def test_records_error_when_item_id_is_invalid(
    mocker, purchase_download_context_factory, bandcamp_item_factory
):
    ctx = purchase_download_context_factory(ign_file_path=None)
    ctx.local_media.write_bandcamp_id.side_effect = ValueError("bad id")
    purchase = bandcamp_item_factory(band_name="Band", item_title="Item", item_id=1)
    record_error = mocker.Mock()

    mark_purchase_downloaded(purchase, ctx, Path("/media/band/item"), record_error)

    record_error.assert_called_once()
    assert "bad id" in record_error.call_args[0][0]
