class BandcampError(ValueError):
    """Base error for any failure interacting with the Bandcamp API."""


class BandcampDownloadUnavailable(BandcampError):
    """Raised when Bandcamp reports no download is available for an item."""


class BandcampDownloadExpired(BandcampError):
    """Raised when Bandcamp reports a purchase's download link has expired."""
