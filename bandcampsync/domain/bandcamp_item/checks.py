"""Pure predicates about an already-built BandcampItem."""

from bandcampsync.domain.bandcamp_item.model import BandcampItem


def is_physical_purchase(item: BandcampItem) -> bool:
    # Note that this only tells us that this is a physical purchase, not if
    # there's also a digital download
    if item.item_type:
        return item.item_type == "package"
    return item.sale_item_type == "p"
