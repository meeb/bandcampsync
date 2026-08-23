"""Tests for bandcampsync.domain.local_media_entry.checks."""

from bandcampsync.domain.local_media_entry import is_locally_downloaded
from tests.factories import make_bandcamp_item


def _item(item_id=123):
    return make_bandcamp_item(item_id=item_id, band_name="Band", item_title="Album")


def test_true_when_item_id_already_known(tmp_path):
    media = {123: tmp_path / "Band" / "Album"}

    assert is_locally_downloaded(media, set(), _item(), tmp_path / "elsewhere") is True


def test_false_when_nothing_known_and_no_id_file(tmp_path):
    local_path = tmp_path / "Band" / "Album"
    local_path.mkdir(parents=True)

    assert is_locally_downloaded({}, set(), _item(), local_path) is False


def test_discovers_and_caches_a_matching_id_file(tmp_path):
    local_path = tmp_path / "Band" / "Album"
    local_path.mkdir(parents=True)
    (local_path / "bandcamp_item_id.txt").write_text("123\n")
    media: dict[int, object] = {}
    item_names: set[tuple[str, str]] = set()

    result = is_locally_downloaded(media, item_names, _item(item_id=123), local_path)

    assert result is True
    assert media == {123: local_path}
    assert ("Band", "Album") in item_names


def test_id_file_present_but_for_a_different_item_still_counts_via_name_match(tmp_path):
    # The directory's own name gets recorded in item_names as a side effect
    # of reading its id file, regardless of whether the id matches - so a
    # mismatched id file still resolves to a (mismatch-warning) True here,
    # same as an id-less album detected purely by directory name would.
    local_path = tmp_path / "Band" / "Album"
    local_path.mkdir(parents=True)
    (local_path / "bandcamp_item_id.txt").write_text("456\n")
    media: dict[int, object] = {}

    result = is_locally_downloaded(media, set(), _item(item_id=123), local_path)

    assert result is True
    assert media == {456: local_path}


def test_true_on_item_name_mismatch_when_directory_already_known(tmp_path):
    local_path = tmp_path / "Band" / "Album"
    local_path.mkdir(parents=True)
    item_names = {("Band", "Album")}

    result = is_locally_downloaded({}, item_names, _item(item_id=999), local_path)

    assert result is True
