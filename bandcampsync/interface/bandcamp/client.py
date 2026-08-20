from bandcampsync.interface.bandcamp.mixins.download import DownloadMixin
from bandcampsync.interface.bandcamp.mixins.fancollection import FanCollectionMixin
from bandcampsync.interface.bandcamp.mixins.identity import IdentityMixin


class Bandcamp(IdentityMixin, FanCollectionMixin, DownloadMixin):
    """Bandcamp API client, composed from mixins named after the URL namespace
    each one talks to (see constants.py's URLS), over a shared session/cookie/
    request base.
    """
