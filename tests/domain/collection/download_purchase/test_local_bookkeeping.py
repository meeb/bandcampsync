"""Tests for bandcampsync.domain.collection.download_purchase.local_bookkeeping."""

from pathlib import Path
from unittest.mock import Mock

from bandcampsync.domain.collection.download_purchase.local_bookkeeping import (
    mark_purchase_downloaded,
)


def test_adds_to_ignores_when_ignore_file_configured():
    ctx = Mock(ign_file_path=Path("/ignores.txt"), ignore_file_writer=Mock(), local_media=Mock())
    purchase = Mock()
    record_error = Mock()

    mark_purchase_downloaded(purchase, ctx, Path("/media/band/item"), record_error)

    ctx.ignore_file_writer.record.assert_called_once_with(purchase)
    ctx.local_media.write_bandcamp_id.assert_not_called()
    record_error.assert_not_called()


def test_writes_bandcamp_id_when_no_ignore_file_configured():
    ctx = Mock(ign_file_path=None, ignore_file_writer=Mock(), local_media=Mock())
    purchase = Mock()
    record_error = Mock()
    local_path = Path("/media/band/item")

    mark_purchase_downloaded(purchase, ctx, local_path, record_error)

    ctx.local_media.write_bandcamp_id.assert_called_once_with(purchase, local_path)
    ctx.ignore_file_writer.record.assert_not_called()
    record_error.assert_not_called()


def test_records_error_when_writing_bandcamp_id_fails():
    ctx = Mock(ign_file_path=None, ignore_file_writer=Mock(), local_media=Mock())
    ctx.local_media.write_bandcamp_id.side_effect = OSError("disk full")
    purchase = Mock(band_name="Band", item_title="Item", item_id=1)
    record_error = Mock()

    mark_purchase_downloaded(purchase, ctx, Path("/media/band/item"), record_error)

    record_error.assert_called_once()
    assert "disk full" in record_error.call_args[0][0]


def test_records_error_when_item_id_is_invalid():
    ctx = Mock(ign_file_path=None, ignore_file_writer=Mock(), local_media=Mock())
    ctx.local_media.write_bandcamp_id.side_effect = ValueError("bad id")
    purchase = Mock(band_name="Band", item_title="Item", item_id=None)
    record_error = Mock()

    mark_purchase_downloaded(purchase, ctx, Path("/media/band/item"), record_error)

    record_error.assert_called_once()
    assert "bad id" in record_error.call_args[0][0]
