"""Session state and low-level HTTP dispatch shared by every Bandcamp client
mixin. Each mixin inherits from this (rather than assuming self.session/
self.request exist via duck typing) so mypy can verify cross-mixin
attribute access, and so Bandcamp's own MRO collapses the diamond into a
single shared instance of this state.
"""

import json
from http.cookies import Morsel, SimpleCookie
from pathlib import Path
from typing import Any, cast

from bs4 import BeautifulSoup
from curl_cffi import requests

from bandcampsync.domain.bandcamp import BandcampError, BandcampItem
from bandcampsync.domain.file_transfer import mask_signed_url
from bandcampsync.domain.logging_setup import get_logger

log = get_logger("bandcamp")


class BandcampClientBase:
    # Declared at class level, not assigned None in __init__: load_cookies()
    # (called at the end of __init__, below) always sets this for real before
    # anything reads it. Assigning it None first would make mypy's flow
    # analysis believe it's still None after the opaque load_cookies() call,
    # marking everything past the following null-check unreachable.
    cookies: SimpleCookie | None

    def __init__(self, cookies: str = "") -> None:
        self.is_authenticated = False
        self.user_id = 0
        self.user_verified = False
        self.purchases: list[BandcampItem] = []
        self.collection_items: list[BandcampItem] = []
        self.load_cookies(cookies)
        assert self.cookies is not None  # noqa: S101 - load_cookies() above always sets it
        cookie_jar: SimpleCookie = self.cookies
        identity: Morsel[str] | None = cookie_jar.get("identity")
        if not identity:
            raise BandcampError(
                "Cookie data does not contain an identity value, make sure your "
                "cookies.txt file is valid and you copied it from an "
                "authenticated browser"
            )
        identity_snip = identity.value[:20]
        log.info(f"Located Bandcamp identity in cookies: {identity_snip}...")
        # Create a "requests" session and map our SimpleCookie to it
        self.session: requests.Session[requests.Response] = requests.Session(impersonate="chrome")
        for cookie_name, morsel in cookie_jar.items():
            self.session.cookies.set(cookie_name, morsel.value)

    def load_cookies(self, cookies_str: str) -> bool:
        self.cookies = SimpleCookie()
        try:
            self.cookies.load(cookies_str)
        except Exception as e:
            raise BandcampError(f"Failed to parse cookies string: {e}") from e
        if len(self.cookies) == 0:
            # Failed to load any cookies, attempt to parse the "cookies" string
            # as a Netscape cookies export
            lines = cookies_str.strip().split("\n")
            for raw_line in lines:
                if raw_line.startswith("#"):
                    continue
                line = raw_line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) == 7:
                    domain, _tailmatch, path, secure, _expires, name, value = parts
                    cookie_string = (
                        f"{name.strip()}={value.strip()}; "
                        f"Domain={domain.strip()}; Path={path.strip()}"
                    )
                    if secure == "TRUE":
                        cookie_string += "; Secure"
                    self.cookies.load(cookie_string)
        return True

    @property
    def cookies_str(self) -> str:
        assert self.cookies is not None  # noqa: S101 - always set by __init__ before this can be called
        return self.cookies.output(header="").strip().replace("\r\n", ";")

    def refresh_cookes(self, file_path: str) -> None:
        log.info(f"Refreshing cookies: {file_path}")
        with Path(file_path).open("w") as f:
            f.write(self.cookies_str)

    def plain_cookies(self) -> dict[str, str]:
        assert self.cookies is not None  # noqa: S101 - always set by __init__ before this can be called
        cookies = {}
        for cookie_value in self.cookies.values():
            cookies[cookie_value.key] = cookie_value.value
        return cookies

    def request(
        self,
        method: str,
        url: str,
        data: Any = None,
        json_data: Any = None,
        is_json: bool = False,
        as_raw: bool = False,
    ) -> Any:
        try:
            # The debug logs do not mask the URL, which may be a security issue if you run
            # with level=logging.DEBUG
            log.debug(f"Making {method} request to {url}")
            # curl_cffi's stub requires an exact-case HTTP-method Literal, but callers
            # here pass mixed-case strings ("get", "POST") intentionally and it accepts
            # any case at runtime - this cast doesn't change what's actually sent.
            response = self.session.request(
                cast(Any, method),
                url,
                cookies=self.plain_cookies(),
                data=data,
                json=json_data,
            )
        except Exception as request_error:
            raise BandcampError(
                f"Failed to make HTTP request to {mask_signed_url(url)}: {request_error}"
            ) from request_error
        if response.status_code != 200:
            raise BandcampError(
                f"Failed to make HTTP request to {mask_signed_url(url)}: "
                f"unknown status code response: {response.status_code}"
            )
        if as_raw:
            return response.text
        elif is_json:
            return json.loads(response.text)
        else:
            return BeautifulSoup(response.text, "html.parser")
