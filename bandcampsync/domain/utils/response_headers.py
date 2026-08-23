from typing import Any


def header_or_default(response: Any, header_name: str, default: str) -> str:
    """Reads one header off an HTTP response, tolerating a response object
    that raises rather than returning a normal missing-key result.
    """
    try:
        return str(response.headers.get(header_name, default))
    except (ValueError, KeyError):
        return default
