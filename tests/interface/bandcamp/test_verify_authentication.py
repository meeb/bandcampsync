"""Tests for bandcampsync.interface.bandcamp.mixins.identity.IdentityMixin."""

from unittest.mock import Mock, patch

import pytest

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.interface.bandcamp import Bandcamp

_PATCH_TARGET = "bandcampsync.interface.bandcamp.mixins.identity.extract_pagedata_from_soup"


@pytest.fixture
def bandcamp() -> Bandcamp:
    instance = Bandcamp("identity=test")
    instance.request = Mock()
    return instance


def _pagedata(**identity_overrides):
    identity = {"fanId": 42, "isFanVerified": True}
    identity.update(identity_overrides)
    return {"pageContext": {"identity": identity}}


def test_authenticated_identity_sets_user_id_and_verification(bandcamp):
    with patch(_PATCH_TARGET, return_value=_pagedata()):
        result = bandcamp.verify_authentication()

    assert result is True
    assert bandcamp.is_authenticated is True
    assert bandcamp.user_id == 42
    assert bandcamp.user_verified is True


def test_non_positive_fan_id_is_not_authenticated(bandcamp):
    with patch(_PATCH_TARGET, return_value=_pagedata(fanId=0)):
        result = bandcamp.verify_authentication()

    assert result is True
    assert bandcamp.is_authenticated is False


def test_missing_page_context_raises():
    bandcamp = Bandcamp("identity=test")
    bandcamp.request = Mock()

    with (
        patch(_PATCH_TARGET, return_value={}),
        pytest.raises(BandcampError, match="pageContext"),
    ):
        bandcamp.verify_authentication()


def test_missing_identity_raises(bandcamp):
    with (
        patch(_PATCH_TARGET, return_value={"pageContext": {}}),
        pytest.raises(BandcampError, match="identity"),
    ):
        bandcamp.verify_authentication()


def test_identity_not_a_dict_raises(bandcamp):
    with (
        patch(_PATCH_TARGET, return_value={"pageContext": {"identity": "nope"}}),
        pytest.raises(BandcampError, match="dictionary"),
    ):
        bandcamp.verify_authentication()


def test_identity_missing_fan_id_raises(bandcamp):
    with (
        patch(_PATCH_TARGET, return_value={"pageContext": {"identity": {"isFanVerified": True}}}),
        pytest.raises(BandcampError, match="identity\\.fan"),
    ):
        bandcamp.verify_authentication()
