"""Deterministic fixture rows in MockRetailerB's native shape.

Every value is invented for framework testing — fictional brands, fictional listings, and
`*.example.test` URLs. Nothing here represents a real retailer, product, or price.

MockRetailerB models a marketplace whose **affiliate feed** delivers flat, snake_case rows with
string amounts in rupees, a `>`-delimited category string, a `|`-delimited spec string, single
letter stock flags, third-party sellers, MPN identifiers instead of GTINs, and a
feed-provided final payable amount.
"""

from types import MappingProxyType
from typing import Any

BASE_URL = "https://mock-retailer-b.example.test"

_ROWS: tuple[dict[str, Any], ...] = (
    {
        "item_id": "880011",
        "name": "Aurora 5G (128GB, Midnight) - Fictional Orchard",
        "mfr": "Fictional Orchard",
        "cat": "electronics>mobiles",
        "cat_slug": "mobiles",
        "specs": "storage=128GB|colour=Midnight",
        "mpn": "FO-AUR-128-MID",
        "mrp": "69999.00",
        "price": "58499.00",
        "final_payable": "58549.00",
        "delivery": "50.00",
        "stock": "Y",
        "seller_code": "B-SELLER-441",
        "seller_name": "Fictional Marketplace Seller 441",
    },
    {
        "item_id": "880042",
        "name": "Aurora 5G (256GB, Midnight) - Fictional Orchard",
        "mfr": "Fictional Orchard",
        "cat": "electronics>mobiles",
        "cat_slug": "mobiles",
        "specs": "storage=256GB|colour=Midnight",
        "mpn": "FO-AUR-256-MID",
        "mrp": "79999.00",
        "price": "71499.00",
        "final_payable": "71499.00",
        "delivery": "0.00",
        "stock": "L",
        "seller_code": "B-SELLER-118",
        "seller_name": "Fictional Marketplace Seller 118",
    },
    {
        "item_id": "915003",
        "name": "Ridgeline Notebook 14 (16GB RAM, 512GB SSD) - Fictional Ridgeline",
        "mfr": "Fictional Ridgeline",
        "cat": "electronics>laptops",
        "cat_slug": "laptops",
        "specs": "ram=16GB|storage=512GB SSD|colour=Slate",
        "mpn": "FR-NB14-16-512",
        "mrp": "94999.00",
        "price": "82999.00",
        "final_payable": "82999.00",
        "delivery": "0.00",
        "stock": "N",
        "seller_code": "B-SELLER-441",
        "seller_name": "Fictional Marketplace Seller 441",
    },
)

ROWS_BY_ITEM_ID: MappingProxyType[str, dict[str, Any]] = MappingProxyType(
    {row["item_id"]: row for row in _ROWS}
)

ROWS: tuple[dict[str, Any], ...] = _ROWS
