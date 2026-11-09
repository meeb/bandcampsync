"""Tests for fitting names to the filesystem, using real directories."""

import pytest

from bandcampsync.names import fit_name, is_usable_name

LONG_NAME = "\u28ce" * 100
ZALGO_NAME = "Album" + "\u0338\u0322\u031b\u0345" * 60


@pytest.mark.parametrize("name", ["Normal Album", "a" * 255, "\u28ce" * 85, "..."])
def test_usable_names_are_never_changed(tmp_path, name):
    assert fit_name(tmp_path, name) == name
    assert fit_name(tmp_path, name, keep_extension=True) == name


@pytest.mark.parametrize(
    "name", ["a" * 256, LONG_NAME, ZALGO_NAME, "a\x00b", "a\ud800b"]
)
def test_unusable_names_can_be_created_after_fitting(tmp_path, name):
    assert is_usable_name(tmp_path, name) is False

    fitted = fit_name(tmp_path, name)

    (tmp_path / fitted).mkdir()
    assert (tmp_path / fitted).is_dir()


def test_combining_marks_are_removed_before_cutting(tmp_path):
    fitted = fit_name(tmp_path, ZALGO_NAME)

    assert fitted.startswith("Album~")
    assert len(fitted) == len("Album~") + 8


def test_fitted_name_is_repeatable(tmp_path):
    assert fit_name(tmp_path, LONG_NAME) == fit_name(tmp_path, LONG_NAME)


def test_similar_long_names_stay_distinct(tmp_path):
    assert fit_name(tmp_path, LONG_NAME + " a") != fit_name(tmp_path, LONG_NAME + " b")


def test_extension_is_kept(tmp_path):
    fitted = fit_name(tmp_path, f"{LONG_NAME}.flac", keep_extension=True)

    assert fitted.endswith(".flac")
    (tmp_path / fitted).write_text("audio")


def test_long_final_part_is_not_treated_as_an_extension(tmp_path):
    name = f"Band. {LONG_NAME}"

    fitted = fit_name(tmp_path, name, keep_extension=True)

    assert fitted.startswith("Band. ")
    (tmp_path / fitted).write_text("audio")


def test_shorter_limit_is_used_when_needed(tmp_path, monkeypatch):
    real = is_usable_name

    def limit_to_143_bytes(directory, name):
        return len(name.encode("utf-8", "surrogatepass")) <= 143 and real(
            directory, name
        )

    monkeypatch.setattr("bandcampsync.names.is_usable_name", limit_to_143_bytes)

    fitted = fit_name(tmp_path, LONG_NAME)

    assert len(fitted.encode()) <= 143


def test_shortened_name_has_no_trailing_dots_or_spaces_before_marker(tmp_path):
    # The cut lands straight after the " . ", which isn't valid to end a name with
    fitted = fit_name(tmp_path, "a" * 243 + " . " + "b" * 30)

    assert fitted.startswith("a" * 243 + "~")
