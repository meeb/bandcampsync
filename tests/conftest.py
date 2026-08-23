"""Shared pytest fixtures: the factory_boy factories in tests/factories.py,
exposed as fixtures (with test-scoped defaults like tmp_path pre-filled
where relevant), plus a ready-to-mock Bandcamp client - so individual test
files don't need to hand-roll their own _item()/_options()/Mock(ctx=...)
helpers.

`mocker` (pytest-mock) is available globally in every test with no import -
prefer it over raw unittest.mock.patch for anything that needs automatic
cleanup.
"""

import pytest

from bandcampsync.interface.bandcamp import Bandcamp
from tests.factories import (
    AlbumFactory,
    BandcampItemFactory,
    BandcampSyncOptionsFactory,
    IgnoreFileWriterFactory,
    IgnoreRulesFactory,
    PhysicalItemFactory,
    PurchaseDownloadContextFactory,
    TrackFactory,
    make_raw_item,
)

# --- BandcampItem -----------------------------------------------------------


@pytest.fixture
def bandcamp_item_factory():
    return BandcampItemFactory


@pytest.fixture
def raw_item_factory():
    """The dict form, for tests feeding raw (unvalidated) API JSON through
    build_items_from_page().
    """
    return make_raw_item


@pytest.fixture
def album_factory():
    return AlbumFactory


@pytest.fixture
def track_factory():
    return TrackFactory


@pytest.fixture
def physical_item_factory():
    """A physical-only purchase (item_type="package", no digital download)."""
    return PhysicalItemFactory


# --- Bandcamp client ------------------------------------------------------


@pytest.fixture
def bandcamp_client() -> Bandcamp:
    """A real, pre-authenticated Bandcamp instance. Mock .request (or
    .verify_authentication/.load_purchases/... ) per-test with `mocker`.
    """
    instance = Bandcamp("identity=test")
    instance.is_authenticated = True
    instance.user_id = 1
    return instance


# --- Options / ignore-entry / download context -----------------------------


@pytest.fixture
def sync_options_factory(tmp_path):
    def make(**overrides):
        overrides.setdefault("dir_path", tmp_path)
        overrides.setdefault("temp_dir_root", tmp_path)
        return BandcampSyncOptionsFactory(**overrides)

    return make


@pytest.fixture
def ignore_rules_factory():
    return IgnoreRulesFactory


@pytest.fixture
def ignore_file_writer_factory():
    return IgnoreFileWriterFactory


@pytest.fixture
def purchase_download_context_factory():
    return PurchaseDownloadContextFactory
