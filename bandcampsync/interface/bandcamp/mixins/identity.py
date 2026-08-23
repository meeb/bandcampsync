"""GET / (URLS["index"]) - the homepage request whose embedded pagedata blob
carries the authenticated fan's identity.
"""

from bandcampsync.domain.bandcamp import BandcampError
from bandcampsync.domain.logging_setup import get_logger
from bandcampsync.interface.bandcamp.base import BandcampClientBase
from bandcampsync.interface.bandcamp.pagedata import extract_pagedata_from_soup
from bandcampsync.interface.bandcamp.urls import construct_url

log = get_logger("bandcamp")


class IdentityMixin(BandcampClientBase):
    def verify_authentication(self) -> bool:
        """Loads the initial account and session data from a request to the index page
        of bandcamp.com. When properly authenticated, an HTML data attribute is present
        that contains account information in an encoded form.
        """
        url = construct_url("index")
        # _dispatch(), not request(): request()'s auth guard would call back
        # into this method while is_authenticated is still False, recursing.
        soup = self._dispatch("get", url)
        pagedata = extract_pagedata_from_soup(soup, id_name="HomepageApp")
        try:
            pagecontext = pagedata["pageContext"]
        except KeyError as e:
            raise BandcampError(
                'Failed to parse pagedata JSON, does not contain an "pageContext" key'
            ) from e
        try:
            identity = pagecontext["identity"]
        except KeyError as e:
            raise BandcampError(
                'Failed to parse pagecontext JSON, does not contain an "identity" key'
            ) from e
        if not isinstance(identity, dict):
            raise BandcampError(
                'Failed to parse pagedata JSON, "identity" is not '
                "a dictionary. Check your cookies.txt file is valid "
                "and up to date"
            )
        try:
            self.user_id = identity["fanId"]
            self.user_verified = identity["isFanVerified"]
        except (KeyError, TypeError) as e:
            raise BandcampError(
                f'Failed to parse pagedata JSON, "identity.fan" seems invalid: {identity}'
            ) from e
        self.is_authenticated = self.user_id > 0
        log.info(f"Loaded page data, session is authenticated for user id: {self.user_id})")
        return True
