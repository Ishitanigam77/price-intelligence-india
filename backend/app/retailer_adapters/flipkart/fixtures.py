"""Deterministic Flipkart Affiliate API fixture payloads.

Shapes follow the documented v1.0 JSON (`productInfoList` / `productBaseInfoV1`). Titles,
product ids, and prices are invented fixtures for tests — they are not live Flipkart
catalogue observations. Field names match official examples at
https://affiliate.flipkart.com/api-docs/af_prod_ref.html
"""

from typing import Any

FIXTURE_PID_IN_STOCK = "MOBFIXAUR128MID1"
FIXTURE_PID_OUT_OF_STOCK = "AUDFIXWAVECHAR1"
FIXTURE_PID_MISSING = "ZZZDOESNOTEXIST1"

_IN_STOCK_BASE: dict[str, Any] = {
    "productId": FIXTURE_PID_IN_STOCK,
    "title": "Fictional Orchard Aurora 5G Smartphone (128 GB, Midnight) [fixture]",
    "productDescription": "Fixture listing used only in adapter tests.",
    "imageUrls": {},
    "maximumRetailPrice": {"amount": 69999, "currency": "INR"},
    "flipkartSellingPrice": {"amount": 58499, "currency": "INR"},
    "flipkartSpecialPrice": {"amount": 58499, "currency": "INR"},
    "productUrl": (
        f"https://dl.flipkart.com/dl/fictional-orchard-aurora/p/itmfixture"
        f"?pid={FIXTURE_PID_IN_STOCK}&affid=example"
    ),
    "productBrand": "Fictional Orchard",
    "inStock": True,
    "codAvailable": True,
    "discountPercentage": 16,
    "offers": [],
    "categoryPath": (
        '[[{"node_id":20001,"node_name":"FLIPKART_TREE"},'
        '{"node_id":20143,"node_name":"Mobiles"},'
        '{"node_id":20144,"node_name":"Handsets"}]]'
    ),
    "styleCode": None,
    "attributes": {
        "size": "16 GB",
        "color": "Midnight",
        "storage": "128 GB",
        "sizeUnit": "",
        "displaySize": "",
    },
}

_OUT_OF_STOCK_BASE: dict[str, Any] = {
    "productId": FIXTURE_PID_OUT_OF_STOCK,
    "title": "Fictional Wavecrest Buds Pro (Charcoal) [fixture]",
    "productDescription": "Fixture listing used only in adapter tests.",
    "imageUrls": {},
    "maximumRetailPrice": {"amount": 4999, "currency": "INR"},
    "flipkartSellingPrice": {"amount": 3299, "currency": "INR"},
    "flipkartSpecialPrice": {"amount": 3299, "currency": "INR"},
    "productUrl": (
        f"https://dl.flipkart.com/dl/fictional-wavecrest-buds/p/itmfixture"
        f"?pid={FIXTURE_PID_OUT_OF_STOCK}&affid=example"
    ),
    "productBrand": "Fictional Wavecrest",
    "inStock": False,
    "codAvailable": False,
    "discountPercentage": 34,
    "offers": [],
    "categoryPath": (
        '[[{"node_id":20001,"node_name":"FLIPKART_TREE"},'
        '{"node_id":20050,"node_name":"Audio"},'
        '{"node_id":20051,"node_name":"Headphones"}]]'
    ),
    "attributes": {
        "size": "",
        "color": "Charcoal",
        "storage": "",
        "sizeUnit": "",
        "displaySize": "",
    },
}

_IN_STOCK_SHIPPING: dict[str, Any] = {
    "shippingCharges": {"amount": 40, "currency": "INR"},
    "sellerName": "Example Studio Seller",
    "sellerAverageRating": 4.2,
    "sellerNoOfRatings": 12,
    "sellerNoOfReviews": 3,
}

_OUT_OF_STOCK_SHIPPING: dict[str, Any] = {
    "shippingCharges": {"amount": 0, "currency": "INR"},
    "sellerName": "Flipkart",
    "sellerAverageRating": 4.5,
    "sellerNoOfRatings": 100,
    "sellerNoOfReviews": 10,
}

SEARCH_RESPONSE: dict[str, Any] = {
    "productInfoList": [
        {"productBaseInfoV1": _IN_STOCK_BASE, "productShippingInfoV1": _IN_STOCK_SHIPPING},
        {
            "productBaseInfoV1": _OUT_OF_STOCK_BASE,
            "productShippingInfoV1": _OUT_OF_STOCK_SHIPPING,
        },
    ]
}

PRODUCT_IN_STOCK_RESPONSE: dict[str, Any] = {
    "productBaseInfoV1": _IN_STOCK_BASE,
    "productShippingInfoV1": _IN_STOCK_SHIPPING,
}

PRODUCT_OUT_OF_STOCK_RESPONSE: dict[str, Any] = {
    "productBaseInfoV1": _OUT_OF_STOCK_BASE,
    "productShippingInfoV1": _OUT_OF_STOCK_SHIPPING,
}

EMPTY_SEARCH_RESPONSE: dict[str, Any] = {"productInfoList": []}

MALFORMED_PRODUCT_RESPONSE: dict[str, Any] = {
    "productBaseInfoV1": {
        "productId": FIXTURE_PID_IN_STOCK,
        # title missing
        "inStock": True,
    }
}
