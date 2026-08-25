"""Deterministic fixture entries in MockRetailerC's native shape.

Every value is invented for framework testing — fictional brands, fictional listings, and
`*.example.test` URLs. Nothing here represents a real retailer, product, or price.

MockRetailerC models a first-party store publishing a nightly **product feed**: nested records,
`Decimal`-style string amounts under `*_inr` keys, a free-text department instead of a category
path, a nested `variant` block, word stock states, a platform fee, and no product identifiers at
all.
"""

from types import MappingProxyType
from typing import Any

BASE_URL = "https://mock-retailer-c.example.test"

#: When this feed snapshot was generated. Fixed so freshness handling is deterministic; a real
#: adapter reads this from the feed's own metadata.
FEED_GENERATED_AT = "2026-01-15T02:00:00+00:00"

_ENTRIES: tuple[dict[str, Any], ...] = (
    {
        "item_code": "C/AUD/0004",
        "title": "Fictional Wavecrest Buds Pro",
        "manufacturer": "Fictional Wavecrest",
        "department": "Audio",
        "department_slug": "audio",
        "variant": {"colour": "Charcoal", "form_factor": "In Ear"},
        "mrp_inr": "4999.00",
        "offer_inr": "3299.00",
        "platform_fee_inr": "49.00",
        "stock_state": "limited",
    },
    {
        "item_code": "C/HOM/0121",
        "title": "Fictional Hearthline Air Purifier 300",
        "manufacturer": "Fictional Hearthline",
        "department": "Home Appliances",
        "department_slug": "home-appliances",
        "variant": {"coverage": "300 sq ft", "colour": "White"},
        "mrp_inr": "18999.00",
        "offer_inr": "14499.00",
        "platform_fee_inr": "0.00",
        "stock_state": "in_stock",
    },
    {
        "item_code": "C/AUD/0088",
        "title": "Fictional Wavecrest Soundbar Mini",
        "manufacturer": "Fictional Wavecrest",
        "department": "Audio",
        "department_slug": "audio",
        "variant": {"channels": "2.1", "colour": "Black"},
        "mrp_inr": "12999.00",
        "offer_inr": "9999.00",
        "platform_fee_inr": "0.00",
        "stock_state": "sold_out",
    },
)

ENTRIES_BY_ITEM_CODE: MappingProxyType[str, dict[str, Any]] = MappingProxyType(
    {entry["item_code"]: entry for entry in _ENTRIES}
)

ENTRIES: tuple[dict[str, Any], ...] = _ENTRIES
