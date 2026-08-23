"""Tests for DownloadMixin.fetch_purchase_file's translation of a rejected
transfer into what that rejection means on Bandcamp specifically.
"""

from io import BytesIO
from unittest.mock import patch

import pytest

from bandcampsync.domain.bandcamp import BandcampDownloadExpired, BandcampError
from bandcampsync.domain.file_transfer import TransferContentRejected
from bandcampsync.interface.bandcamp import Bandcamp


@pytest.fixture
def bandcamp() -> Bandcamp:
    instance = Bandcamp("identity=test")
    instance.is_authenticated = True
    instance.user_id = 1
    return instance


def test_returns_the_content_type_on_success(bandcamp: Bandcamp):
    with patch(
        "bandcampsync.interface.bandcamp.mixins.download.stream_url_to_file",
        return_value="audio/flac",
    ):
        content_type = bandcamp.fetch_purchase_file("https://example.com/file", BytesIO())

    assert content_type == "audio/flac"


def test_translates_an_expired_page_rejection(bandcamp: Bandcamp):
    rejection = TransferContentRejected("rejected", "text/html", "<html>expired</html>")
    with (
        patch(
            "bandcampsync.interface.bandcamp.mixins.download.stream_url_to_file",
            side_effect=rejection,
        ),
        patch(
            "bandcampsync.interface.bandcamp.mixins.download.is_expired_download_page",
            return_value=True,
        ),
        pytest.raises(BandcampDownloadExpired),
    ):
        bandcamp.fetch_purchase_file("https://example.com/file", BytesIO())


def test_translates_a_non_expired_rejection_into_a_bandcamp_error(bandcamp: Bandcamp):
    rejection = TransferContentRejected("rejected", "text/html", "<html>something else</html>")
    with (
        patch(
            "bandcampsync.interface.bandcamp.mixins.download.stream_url_to_file",
            side_effect=rejection,
        ),
        patch(
            "bandcampsync.interface.bandcamp.mixins.download.is_expired_download_page",
            return_value=False,
        ),
        pytest.raises(BandcampError) as excinfo,
    ):
        bandcamp.fetch_purchase_file("https://example.com/file", BytesIO())

    assert not isinstance(excinfo.value, BandcampDownloadExpired)
    assert "text/html" in str(excinfo.value)
