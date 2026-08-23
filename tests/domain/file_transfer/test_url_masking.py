"""Tests for bandcampsync.domain.file_transfer.url_masking."""

from bandcampsync.domain.file_transfer.url_masking import mask_signed_url


def test_leaves_unsigned_urls_untouched():
    url = "https://example.com/file.flac?foo=bar"
    assert mask_signed_url(url) == url


def test_masks_signature_parameter():
    url = "https://example.com/file.flac?foo=bar&sig=abc123&other=1"
    assert mask_signed_url(url) == "https://example.com/file.flac?foo=bar&sig=[masked]&other=1"


def test_masks_token_parameter():
    url = "https://example.com/file.flac?foo=bar&sig=abc123&token=secret"
    masked = mask_signed_url(url)
    assert "token=[masked]" in masked
    assert "secret" not in masked
