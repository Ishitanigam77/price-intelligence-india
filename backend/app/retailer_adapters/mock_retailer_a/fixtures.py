"""Deterministic fixture payloads in MockRetailerA's native shape.

Every value here is invented for framework testing: fictional brand, fictional product names,
`*.example.test` URLs, and prices that are obviously not scraped from anywhere. Nothing in this
module represents a real retailer, product, or price.

MockRetailerA models a retailer with an **official API** returning camelCase JSON, integer
**paise** amounts, category paths as arrays, and first-party fulfilment.
"""

from types import MappingProxyType
from typing import Any

#: Base URL for fabricated listing links. `.test` is reserved by RFC 2606 and never resolves.
BASE_URL = "https://mock-retailer-a.example.test"

_LISTINGS: tuple[dict[str, Any], ...] = (
    {
        "sku": "A-MOB-1001",
        "productName": "Fictional Orchard Aurora 5G Smartphone (128 GB, Midnight)",
        "brand": "Fictional Orchard",
        "categoryPath": ["Electronics", "Mobiles"],
        "categorySlug": "mobiles",
        "attributes": {"Storage": "128 GB", "Colour": "Midnight"},
        "gtin": "0000000001001",
        "listPriceInPaise": 6999900,
        "sellingPriceInPaise": 5999900,
        "stock": "IN_STOCK",
        "fulfilledBy": {"id": "A-SELLER-0", "name": "Fictional Mock Mart A", "firstParty": True},
    },
    {
        "sku": "A-MOB-1002",
        "productName": "Fictional Orchard Aurora 5G Smartphone (256 GB, Midnight)",
        "brand": "Fictional Orchard",
        "categoryPath": ["Electronics", "Mobiles"],
        "categorySlug": "mobiles",
        "attributes": {"Storage": "256 GB", "Colour": "Midnight"},
        "gtin": "0000000001002",
        "listPriceInPaise": 7999900,
        "sellingPriceInPaise": 7449900,
        "stock": "LIMITED",
        "fulfilledBy": {"id": "A-SELLER-0", "name": "Fictional Mock Mart A", "firstParty": True},
    },
    {
        "sku": "A-AUD-2001",
        "productName": "Fictional Wavecrest Buds Pro (Wireless Earbuds, Charcoal)",
        "brand": "Fictional Wavecrest",
        "categoryPath": ["Electronics", "Audio"],
        "categorySlug": "audio",
        "attributes": {"Colour": "Charcoal", "Form Factor": "In Ear"},
        "gtin": "0000000002001",
        "listPriceInPaise": 499900,
        "sellingPriceInPaise": 349900,
        "stock": "OUT_OF_STOCK",
        "fulfilledBy": {"id": "A-SELLER-0", "name": "Fictional Mock Mart A", "firstParty": True},
    },
)

#: Read-only view keyed by native SKU, so a caller cannot mutate the fixtures.
LISTINGS_BY_SKU: MappingProxyType[str, dict[str, Any]] = MappingProxyType(
    {listing["sku"]: listing for listing in _LISTINGS}
)

LISTINGS: tuple[dict[str, Any], ...] = _LISTINGS
