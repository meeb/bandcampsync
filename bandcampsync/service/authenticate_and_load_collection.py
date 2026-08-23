"""Builds the Bandcamp collection session via the injected factory,
authenticates it, and paginates the collection up to the checkpoint or
until_date cutoff.
"""

import logging
from collections.abc import Callable

from bandcampsync.domain.bandcamp import BandcampFullSession
from bandcampsync.domain.collection import PurchaseDateParser, should_stop_loading_purchase
from bandcampsync.domain.options import BandcampSyncOptions

log = logging.getLogger("sync")


def authenticate_and_load_collection(
    bandcamp_factory: Callable[[str], BandcampFullSession],
    options: BandcampSyncOptions,
    date_parser: PurchaseDateParser,
    checkpoint_token: str | None,
) -> BandcampFullSession:
    """Builds, authenticates, and loads purchases for one sync run.

    Args:
        bandcamp_factory: Builds the session from options.cookies. Swap in a
            fake to avoid hitting bandcamp.com in tests.
    """
    bandcamp = bandcamp_factory(options.cookies)
    bandcamp.verify_authentication()
    bandcamp.load_purchases(
        stop_when=lambda item: should_stop_loading_purchase(
            item, date_parser, checkpoint_token, options.until_date
        )
    )
    if options.until_date:
        log.info(
            "Will stop after processing purchases on or after: "
            f"{options.until_date.isoformat()} (purchase date GMT)"
        )
    return bandcamp
