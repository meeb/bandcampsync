class TransferBadStatusCode(ValueError):
    pass


class TransferContentRejected(ValueError):
    """Raised when a streamed response has a disallowed content type.

    Carries the response body so a caller with more context (e.g. Bandcamp's own
    page markup) can decide what the rejection actually means, without this generic
    transport layer needing to know.
    """

    def __init__(self, message: str, content_type: str, body: str) -> None:
        super().__init__(message)
        self.content_type = content_type
        self.body = body
