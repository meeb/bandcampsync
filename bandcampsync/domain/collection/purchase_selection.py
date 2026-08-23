"""Pure logic for deciding which purchased items to sync and in what order:
newest-first by purchase date, stopping at a collection checkpoint token or
an --until-date cutoff.
"""

import logging
from datetime import date, datetime, timezone

from bandcampsync.domain.bandcamp import BandcampItem

log = logging.getLogger("sync")


def item_token(item: BandcampItem) -> str | None:
    token = getattr(item, "token", None)
    if isinstance(token, str) and token:
        return token
    return None


class PurchaseDateParser:
    """Parses a purchase date, warning at most once per parser instance (not
    once per item) if the format is unrecognised.
    """

    def __init__(self) -> None:
        self._warned = False

    def parse(self, item: BandcampItem) -> datetime | None:
        purchased = getattr(item, "purchased", None)
        if not purchased or not isinstance(purchased, str):
            return None
        if purchased.endswith(" GMT"):
            try:
                dt = datetime.strptime(purchased, "%d %b %Y %H:%M:%S GMT")
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        try:
            dt = datetime.strptime(purchased, "%d %b %Y %H:%M:%S %Z")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            if not self._warned:
                log.warning(
                    f'Unable to parse purchase date "{purchased}". '
                    "Date cutoffs may not behave as expected."
                )
                self._warned = True
        return None


def should_stop_loading_purchase(
    item: BandcampItem,
    date_parser: PurchaseDateParser,
    checkpoint_token: str | None,
    until_date: date | None,
) -> bool:
    if until_date:
        purchase_dt = date_parser.parse(item)
        if purchase_dt is not None and purchase_dt.date() < until_date:
            return True
    if checkpoint_token:
        token = item_token(item)
        if token and token == checkpoint_token:
            log.info("Reached last known collection checkpoint, stopping pagination")
            return True
    return False


def ordered_purchases(
    purchases: list[BandcampItem], date_parser: PurchaseDateParser
) -> list[BandcampItem]:
    items = list(purchases)
    if not items:
        return []
    indexed: list[tuple[int, BandcampItem, datetime | None]] = []
    any_dates = False
    for idx, item in enumerate(items):
        purchase_dt = date_parser.parse(item)
        if purchase_dt is not None:
            any_dates = True
        indexed.append((idx, item, purchase_dt))

    if not any_dates:
        return [item for _, item, _ in indexed]

    def sort_key(entry: tuple[int, BandcampItem, datetime | None]) -> tuple[int, datetime]:
        _, _, purchase_datetime = entry
        if purchase_datetime is None:
            return 0, datetime.min.replace(tzinfo=timezone.utc)
        return 1, purchase_datetime

    indexed.sort(key=sort_key, reverse=True)
    return [item for _, item, _ in indexed]


def select_items_to_sync(
    purchases: list[BandcampItem],
    date_parser: PurchaseDateParser,
    checkpoint_token: str | None,
    until_date: date | None,
) -> list[BandcampItem]:
    items = ordered_purchases(purchases, date_parser)
    if not items:
        return []

    selected = []
    for item in items:
        token = item_token(item)
        if checkpoint_token and token and token == checkpoint_token:
            log.info("Stopping at collection checkpoint item")
            break

        if until_date:
            purchase_dt = date_parser.parse(item)
            if purchase_dt is not None and purchase_dt.date() < until_date:
                log.info(f"Stopping before items older than {until_date.isoformat()}")
                break

        selected.append(item)
    return selected
