"""The union of BandcampSession and BandcampCollectionSession: what
service/sync_collection.py needs from a single Bandcamp instance that it
both authenticates/paginates with and hands to the download_purchase
pipeline afterwards.

Neither narrower protocol grows to cover the other's members - each stays
scoped to what its own consumer (download_purchase's context, or
sync_collection's setup) actually needs (interface segregation). This one
exists only to give sync_collection's Bandcamp session a static type that
satisfies both consumers at once; the concrete Bandcamp class already
satisfies it structurally without knowing it exists.
"""

from typing import Protocol

from bandcampsync.domain.bandcamp.collection_session import BandcampCollectionSession
from bandcampsync.domain.bandcamp.session import BandcampSession


class BandcampFullSession(BandcampSession, BandcampCollectionSession, Protocol):
    pass
