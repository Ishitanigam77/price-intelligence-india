"""Deterministic Creators API fixture payloads for Amazon.in adapter tests.

These objects follow the documented Creators API JSON shape (lowerCamelCase `searchResult` /
`itemResults`, `offersV2.listings`, `itemInfo`). Titles, ASINs, and prices are invented
fixtures for tests — they are not live Amazon.in catalogue observations.
"""

from typing import Any

#: Fictional ASIN-shaped ids (10 characters) used only in fixtures.
FIXTURE_ASIN_IN_STOCK = "B00FIX001A"
FIXTURE_ASIN_OUT_OF_STOCK = "B00FIX002B"
FIXTURE_ASIN_MISSING = "B00FIX000X"

TOKEN_RESPONSE: dict[str, Any] = {
    "access_token": "test-access-token-not-a-secret",
    "scope": "creatorsapi::default",
    "token_type": "bearer",
    "expires_in": 3600,
}

_IN_STOCK_ITEM: dict[str, Any] = {
    "asin": FIXTURE_ASIN_IN_STOCK,
    "detailPageURL": (
        f"https://www.amazon.in/dp/{FIXTURE_ASIN_IN_STOCK}?tag=example-21&linkCode=ogi"
    ),
    "parentASIN": "B00FIX000P",
    "browseNodeInfo": {
        "browseNodes": [
            {"id": "1805560031", "displayName": "Electronics", "isRoot": False},
            {"id": "1389401031", "displayName": "Mobiles", "isRoot": False},
        ]
    },
    "itemInfo": {
        "title": {
            "displayValue": "Fictional Orchard Aurora 5G Smartphone (128 GB, Midnight) [fixture]",
            "label": "Title",
            "locale": "en_IN",
        },
        "byLineInfo": {"brand": {"displayValue": "Fictional Orchard", "locale": "en_IN"}},
        "classifications": {
            "productGroup": {"displayValue": "Wireless", "locale": "en_IN"},
            "binding": {"displayValue": "Electronics", "locale": "en_IN"},
        },
        "productInfo": {
            "color": {"displayValue": "Midnight", "locale": "en_IN"},
            "size": {"displayValue": "128 GB", "locale": "en_IN"},
        },
        "externalIds": {
            "eaNs": {"displayValues": ["8900000001001"], "label": "EAN", "locale": "en_IN"},
            "upCs": {"displayValues": ["012345678905"], "label": "UPC", "locale": "en_IN"},
        },
        "manufactureInfo": {"itemPartNumber": {"displayValue": "FO-AUR-128-MID"}},
    },
    "variationAttributes": [
        {"name": "Colour", "value": "Midnight"},
        {"name": "Storage", "value": "128 GB"},
    ],
    "offersV2": {
        "listings": [
            {
                "isBuyBoxWinner": True,
                "merchantInfo": {"id": "A21EXAMPLE", "name": "Amazon"},
                "availability": {
                    "type": "IN_STOCK",
                    "message": "In stock.",
                    "maxOrderQuantity": 12,
                },
                "price": {
                    "money": {
                        "amount": 59999.00,
                        "currency": "INR",
                        "displayAmount": "₹59,999.00",
                    },
                    "savingBasis": {
                        "money": {
                            "amount": 69999.00,
                            "currency": "INR",
                            "displayAmount": "₹69,999.00",
                        }
                    },
                },
            }
        ]
    },
}

_OUT_OF_STOCK_ITEM: dict[str, Any] = {
    "asin": FIXTURE_ASIN_OUT_OF_STOCK,
    "detailPageURL": (
        f"https://www.amazon.in/dp/{FIXTURE_ASIN_OUT_OF_STOCK}?tag=example-21&linkCode=ogi"
    ),
    "itemInfo": {
        "title": {
            "displayValue": "Fictional Wavecrest Buds Pro (Charcoal) [fixture]",
            "label": "Title",
            "locale": "en_IN",
        },
        "byLineInfo": {"brand": {"displayValue": "Fictional Wavecrest", "locale": "en_IN"}},
        "productInfo": {"color": {"displayValue": "Charcoal", "locale": "en_IN"}},
        "externalIds": {},
    },
    "variationAttributes": [{"name": "Colour", "value": "Charcoal"}],
    "offersV2": {
        "listings": [
            {
                "isBuyBoxWinner": True,
                "merchantInfo": {"id": "A22MARKET", "name": "Example Marketplace Seller"},
                "availability": {"type": "OUT_OF_STOCK", "message": "Currently unavailable."},
                "price": {
                    "money": {
                        "amount": 3499.00,
                        "currency": "INR",
                        "displayAmount": "₹3,499.00",
                    },
                    "savingBasis": {
                        "money": {
                            "amount": 4999.00,
                            "currency": "INR",
                            "displayAmount": "₹4,999.00",
                        }
                    },
                },
            }
        ]
    },
}

SEARCH_RESPONSE: dict[str, Any] = {
    "searchResult": {
        "totalResultCount": 2,
        "searchURL": "https://www.amazon.in/s?k=fictional+orchard&tag=example-21",
        "items": [_IN_STOCK_ITEM, _OUT_OF_STOCK_ITEM],
    }
}

GET_ITEMS_IN_STOCK_RESPONSE: dict[str, Any] = {
    "itemResults": {"items": [_IN_STOCK_ITEM]},
}

GET_ITEMS_OUT_OF_STOCK_RESPONSE: dict[str, Any] = {
    "itemResults": {"items": [_OUT_OF_STOCK_ITEM]},
}

GET_ITEMS_NOT_FOUND_RESPONSE: dict[str, Any] = {
    "errors": [
        {
            "code": "ItemNotAccessible",
            "message": "The ItemId is not accessible through the Creators API.",
        }
    ],
    "itemResults": {"items": []},
}

MALFORMED_ITEM_RESPONSE: dict[str, Any] = {
    "itemResults": {
        "items": [
            {
                "asin": FIXTURE_ASIN_IN_STOCK,
                # Title missing — cannot map to RetailerProduct.
                "offersV2": {"listings": []},
            }
        ]
    }
}
