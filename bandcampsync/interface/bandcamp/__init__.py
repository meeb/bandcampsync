"""The outbound Bandcamp API client: an adapter that talks to bandcamp.com and
produces domain types (bandcamp_item.BandcampItem, bandcamp.BandcampError)
from it.
"""

from bandcampsync.interface.bandcamp.client import Bandcamp

__all__ = ["Bandcamp"]
