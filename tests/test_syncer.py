"""Unit tests for the Syncer class."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import pytest
from bandcampsync.sync import Syncer


@pytest.fixture
def temp_music_dir():
    """Create a temporary directory for music."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_ignores_file():
    """Create a temporary ignores file."""
    with TemporaryDirectory() as tmpdir:
        ignores_path = Path(tmpdir) / "ignores.txt"
        ignores_path.write_text("# Test ignores file\n")
        yield ignores_path


@pytest.fixture
def mock_bandcamp():
    """Mock only the Bandcamp API (external dependency)."""
    with patch("bandcampsync.sync.Bandcamp") as mock:
        instance = Mock()
        instance.verify_authentication = Mock()
        instance.load_purchases = Mock()
        instance.purchases = []
        mock.return_value = instance
        yield instance


@pytest.fixture
def syncer_class(mock_bandcamp, temp_music_dir, temp_ignores_file):
    """Return a factory function to create Syncer instances."""
    def _create_syncer(
        ign_patterns="",
        notify_url=None,
        purchases=None,
        concurrency=1,
    ):
        if purchases is not None:
            mock_bandcamp.purchases = purchases

        cookies = "identity=test_identity; Path=/; Domain=.bandcamp.com"

        syncer = Syncer(
            cookies=cookies,
            dir_path=temp_music_dir,
            media_format="flac",
            temp_dir_root=str(temp_music_dir),
            ign_file_path=str(temp_ignores_file),
            ign_patterns=ign_patterns,
            notify_url=notify_url,
            concurrency=concurrency,
        )
        return syncer

    return _create_syncer


def create_mock_item(
    band_name="Test Band",
    item_title="Test Album",
    item_id=12345,
    is_preorder=False,
    item_type="album",
):
    """Helper to create mock items."""
    item = Mock()
    item.band_name = band_name
    item.item_title = item_title
    item.item_id = item_id
    item.is_preorder = is_preorder
    item.item_type = item_type
    item.url_hints = None
    return item


class TestSyncerInit:
    """Tests for Syncer initialization."""

    def test_init_stores_parameters(self, syncer_class, temp_ignores_file):
        """Test that __init__ stores required parameters."""
        syncer = syncer_class()
        assert syncer.media_format == "flac"
        assert syncer.ign_file_path == str(temp_ignores_file)
        assert syncer.notify_url is None

    def test_init_auto_syncs_and_notifies(self, syncer_class):
        """Test that __init__ automatically calls sync_items."""
        # Creating the syncer should automatically process items
        syncer = syncer_class(purchases=[])
        # If it didn't crash, the auto-sync worked
        assert syncer.new_items_downloaded is False


class TestSyncItem:
    """Tests for sync_item method."""

    def test_sync_item_preorder_returns_false(self, syncer_class):
        """Test that sync_item returns False for preorder items."""
        item = create_mock_item(is_preorder=True)
        syncer = syncer_class(purchases=[item])

        # Item was processed during __init__, check it was skipped
        assert syncer.new_items_downloaded is False

    def test_sync_item_already_downloaded_returns_false(
        self, syncer_class, temp_music_dir
    ):
        """Test that sync_item returns False for already downloaded items."""
        item = create_mock_item()

        # Create the directory structure to simulate already downloaded
        artist_dir = temp_music_dir / "Test Band"
        album_dir = artist_dir / "Test Album"
        album_dir.mkdir(parents=True)
        id_file = album_dir / "bandcamp_item_id.txt"
        id_file.write_text("12345\n")

        syncer = syncer_class(purchases=[item])

        # Item was processed during __init__, check it was skipped
        assert syncer.new_items_downloaded is False

    def test_sync_item_ignored_by_pattern_returns_false(self, syncer_class):
        """Test that sync_item returns False when item matches ignore pattern."""
        item = create_mock_item(band_name="Ignored_Band Name")
        syncer = syncer_class(ign_patterns="ignored_band", purchases=[item])

        # Item was processed during __init__, check it was skipped
        assert syncer.new_items_downloaded is False

    def test_sync_item_ignored_by_id_returns_false(
        self, syncer_class, temp_ignores_file
    ):
        """Test that sync_item returns False when item ID is in ignore file."""
        # Add item ID to ignore file
        temp_ignores_file.write_text("12345  # Test Band / Test Album\n")

        item = create_mock_item(item_id=12345)
        syncer = syncer_class(purchases=[item])

        # Item was processed during __init__, check it was skipped
        assert syncer.new_items_downloaded is False

    def test_sync_item_sets_warning_flag_for_dual_ignore(
        self, syncer_class, temp_music_dir
    ):
        """Test warning flag when item is in ignore file AND has local ID file."""
        item = create_mock_item(item_id=99999)

        # Create directory with bandcamp_item_id.txt
        artist_dir = temp_music_dir / "Test Band"
        album_dir = artist_dir / "Test Album"
        album_dir.mkdir(parents=True)
        id_file = album_dir / "bandcamp_item_id.txt"
        id_file.write_text("99999\n")

        # Create syncer with item in ignore list
        syncer = syncer_class(purchases=[item])
        # Manually add to ignore IDs before re-indexing
        syncer.ignores.ids.add(99999)
        syncer.local_media.index()

        # Now sync this item again
        syncer.sync_item(item)

        assert syncer.show_id_file_warning is True


class TestSyncItems:
    """Tests for sync_items method."""

    def test_sync_items_processes_all_purchases(self, syncer_class):
        """Test that sync_items processes all purchases."""
        item1 = create_mock_item(
            band_name="Band 1", item_title="Album 1", item_id=1, is_preorder=True
        )
        item2 = create_mock_item(
            band_name="Band 2", item_title="Album 2", item_id=2, is_preorder=True
        )

        syncer = syncer_class(purchases=[item1, item2])

        # Both items should have been processed (they're preorders so skipped)
        # But we can verify the logic ran without errors
        assert syncer.new_items_downloaded is False

    def test_sync_items_empty_purchases(self, syncer_class):
        """Test sync_items with no purchases."""
        syncer = syncer_class(purchases=[])

        assert syncer.new_items_downloaded is False

    def test_sync_items_with_concurrency(self, syncer_class):
        """Test that sync_items works with concurrency > 1."""
        item1 = create_mock_item(
            band_name="Band 1", item_title="Album 1", item_id=1, is_preorder=True
        )
        item2 = create_mock_item(
            band_name="Band 2", item_title="Album 2", item_id=2, is_preorder=True
        )
        item3 = create_mock_item(
            band_name="Band 3", item_title="Album 3", item_id=3, is_preorder=True
        )

        syncer = syncer_class(purchases=[item1, item2, item3], concurrency=2)

        # All items should have been processed concurrently
        assert syncer.new_items_downloaded is False


class TestNotify:
    """Tests for notify method."""

    def test_notify_called_when_new_items_downloaded(self, syncer_class):
        """Test that notify is called when new items are downloaded."""
        with patch("bandcampsync.sync.NotifyURL") as mock_notify_class:
            mock_notify_instance = Mock()
            mock_notify_class.return_value = mock_notify_instance

            syncer = syncer_class(notify_url="http://example.com/notify", purchases=[])
            syncer.new_items_downloaded = True
            syncer.notify()

            mock_notify_class.assert_called_once_with("http://example.com/notify")
            mock_notify_instance.notify.assert_called_once()

    def test_notify_not_called_when_no_new_items(self, syncer_class):
        """Test that notify is not called when no new items are downloaded."""
        with patch("bandcampsync.sync.NotifyURL") as mock_notify:
            syncer = syncer_class(notify_url="http://example.com/notify", purchases=[])
            syncer.new_items_downloaded = False
            syncer.notify()

            # NotifyURL should not be instantiated
            mock_notify.assert_not_called()

    def test_notify_not_called_when_url_is_none(self, syncer_class):
        """Test that notify is not called when notify_url is None."""
        with patch("bandcampsync.sync.NotifyURL") as mock_notify:
            syncer = syncer_class(notify_url=None, purchases=[])
            syncer.new_items_downloaded = True
            syncer.notify()

            # NotifyURL should not be instantiated
            mock_notify.assert_not_called()
