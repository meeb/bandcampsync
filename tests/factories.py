"""Shared test factories, built with factory_boy against the real domain
classes (pydantic models and plain dataclasses alike - factory.Factory just
calls the model's constructor with the declared/overridden kwargs, so it
works for both without any pydantic-specific magic).

Field defaults below mirror a real captured collection API response
(tests/domain/bandcamp_item/data/collection-item-digital-only.json), not
guessed-at values - see docs/hex_migration_hour.md for how that was
verified against a live account.

Usage: call a factory class directly to build an instance, overriding only
the fields your test cares about - e.g. `BandcampItemFactory(item_id=5)`.
Prefer the conftest.py fixtures (`bandcamp_item_factory`, `album_factory`,
...) inside tests rather than importing these classes directly, so a test's
dependencies stay visible in its signature.
"""

from unittest.mock import Mock

import factory

from bandcampsync.domain.bandcamp_item import BandcampItem
from bandcampsync.domain.collection.download_purchase import PurchaseDownloadContext
from bandcampsync.domain.ignore_entry import IgnoreFileLayout, IgnoreFileWriter, IgnoreRules
from bandcampsync.domain.options import BandcampSyncOptions


class BandcampItemFactory(factory.Factory):
    class Meta:
        model = BandcampItem

    item_id = factory.Sequence(lambda n: n + 1)
    band_name = "Arab Strap"
    item_title = "Primavera Sound: Live in Barcelona (2017)"
    item_type = "album"
    hidden = None
    token = factory.Sequence(lambda n: f"{1700000000 + n}:{1000000000 + n}:a::")
    sale_item_type = "p"
    sale_item_id = factory.Sequence(lambda n: 100000000 + n)
    is_preorder = False
    url_hints = None
    purchased = "07 Jul 2020 01:34:59 GMT"


class AlbumFactory(BandcampItemFactory):
    item_type = "album"


class TrackFactory(BandcampItemFactory):
    item_type = "track"


class PhysicalItemFactory(BandcampItemFactory):
    """A physical-only purchase: no digital download available."""

    item_type = "package"
    sale_item_type = "p"


def make_raw_item(**overrides: object) -> dict[str, object]:
    """The dict form, for tests feeding raw (unvalidated) API JSON through
    build_items_from_page() rather than constructing BandcampItem directly.
    """
    return BandcampItemFactory(**overrides).model_dump()


class IgnoreRulesFactory(factory.Factory):
    class Meta:
        model = IgnoreRules

    ids = frozenset()
    band_patterns = ()


class IgnoreFileLayoutFactory(factory.Factory):
    class Meta:
        model = IgnoreFileLayout

    lines = factory.LazyFunction(list)
    insert_index = -1


class IgnoreFileWriterFactory(factory.Factory):
    class Meta:
        model = IgnoreFileWriter

    ign_file_path = None
    layout = factory.SubFactory(IgnoreFileLayoutFactory)


class BandcampSyncOptionsFactory(factory.Factory):
    """dir_path has no sensible static default (it needs a real, test-scoped
    directory) so it's left undeclared - the underlying dataclass requires
    it, so omitting an override raises a clear TypeError rather than
    silently building an unusable options object. Prefer the
    sync_options_factory fixture in conftest.py, which pre-fills dir_path/
    temp_dir_root from pytest's tmp_path.
    """

    class Meta:
        model = BandcampSyncOptions

    cookies = "identity=test"
    media_format = "flac"
    temp_dir_root = None
    ign_file_path = None
    ign_patterns = ""
    notify_url = None


def _default_local_media() -> Mock:
    # is_locally_downloaded defaults to False, not an auto-generated (and
    # therefore truthy) Mock - most tests want "nothing found" as the
    # baseline and only override this when they're specifically testing
    # the already-downloaded path.
    return Mock(is_locally_downloaded=Mock(return_value=False))


class PurchaseDownloadContextFactory(factory.Factory):
    """bandcamp/local_media default to plain Mocks, since tests almost
    always need to control their behavior - override with real instances if
    a test needs one.
    """

    class Meta:
        model = PurchaseDownloadContext

    bandcamp = factory.LazyFunction(Mock)
    local_media = factory.LazyFunction(_default_local_media)
    ignore_rules = factory.SubFactory(IgnoreRulesFactory)
    ignore_file_writer = factory.SubFactory(IgnoreFileWriterFactory)
    media_format = "flac"
    temp_dir_root = None
    max_retries = 3
    retry_wait = 0
    dry_run = False
    skip_hidden = False
    ign_file_path = None
