class BandcampError(ValueError):
    pass


class BandcampDownloadUnavailable(BandcampError):
    pass


class BandcampDownloadExpired(BandcampError):
    pass
