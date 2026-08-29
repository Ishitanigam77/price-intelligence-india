"""Native Flipkart Affiliate API payload → standardized models.

This is the only module that understands Flipkart field names (`productBaseInfoV1`,
`flipkartSellingPrice`, `inStock`, encoded `categoryPath`). Nothing downstream sees them.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.retailer_adapters.base.errors import InvalidRetailerResponseError
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    PriceObservation,
    RetailerProduct,
    SellerInformation,
)

_SOURCE_TYPE = SourceType.AFFILIATE_FEED
_CONFIDENCE = ConfidenceLevel.HIGH
_FIRST_PARTY_SELLERS = frozenset({"flipkart", "ws retail", "flipkart.com"})


def _inr_amount(node: Any, *, retailer_id: str, field_name: str) -> Decimal | None:
    if node is None:
        return None
    if isinstance(node, (int, float, Decimal, str)):
        raw = node
    elif isinstance(node, dict):
        if node.get("amount") is None:
            return None
        raw = node["amount"]
    else:
        raise InvalidRetailerResponseError(
            f"Expected a money object for {field_name}.",
            retailer_id=retailer_id,
        )
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidRetailerResponseError(
            f"Expected a numeric amount for {field_name}.",
            retailer_id=retailer_id,
        ) from exc
    if amount < 0:
        raise InvalidRetailerResponseError(
            f"Amount for {field_name} was negative.",
            retailer_id=retailer_id,
        )
    return amount.quantize(Decimal("0.01"))


def parse_category_path(raw: Any) -> tuple[str, ...]:
    """Parse Flipkart's encoded categoryPath JSON into a display-name tuple."""
    parsed: Any = raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return ()
    if not isinstance(parsed, list) or not parsed:
        return ()
    first = parsed[0] if parsed and isinstance(parsed[0], list) else parsed
    if not isinstance(first, list):
        return ()
    names: list[str] = []
    for node in first:
        if not isinstance(node, dict):
            continue
        name = node.get("node_name") or node.get("title") or node.get("nodeName")
        if isinstance(name, str) and name.strip() and name.strip().upper() != "FLIPKART_TREE":
            names.append(name.strip())
    return tuple(names)


def _base_and_shipping(
    payload: dict[str, Any], *, retailer_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(payload.get("productBaseInfoV1"), dict):
        shipping = payload.get("productShippingInfoV1")
        return payload["productBaseInfoV1"], shipping if isinstance(shipping, dict) else {}
    nested = payload.get("productBaseInfo")
    if isinstance(nested, dict):
        identifier_raw = nested.get("productIdentifier")
        identifier = identifier_raw if isinstance(identifier_raw, dict) else {}
        attributes_raw = nested.get("productAttributes")
        attributes = attributes_raw if isinstance(attributes_raw, dict) else {}
        merged = {**attributes, **identifier}
        shipping = payload.get("productShippingBaseInfo")
        return merged, shipping if isinstance(shipping, dict) else {}
    if "productId" in payload:
        return payload, {}
    raise InvalidRetailerResponseError(
        "Flipkart payload did not include productBaseInfoV1.",
            retailer_id=retailer_id,
    )


def product_entries_from_search(
    payload: dict[str, Any], *, retailer_id: str
) -> list[dict[str, Any]]:
    items = payload.get("productInfoList")
    if items is None:
        raise InvalidRetailerResponseError(
            "Search response did not include productInfoList.",
            retailer_id=retailer_id,
        )
    if not isinstance(items, list):
        raise InvalidRetailerResponseError(
            "productInfoList was not a list.",
            retailer_id=retailer_id,
        )
    return [item for item in items if isinstance(item, dict)]


def product_id(base: dict[str, Any], *, retailer_id: str) -> str:
    pid = base.get("productId")
    if not isinstance(pid, str) or not pid.strip():
        raise InvalidRetailerResponseError(
            "A product was missing its productId.",
            retailer_id=retailer_id,
        )
    return pid.strip()


def product_title(base: dict[str, Any], *, retailer_id: str) -> str:
    title = base.get("title")
    if not isinstance(title, str) or not title.strip():
        raise InvalidRetailerResponseError(
            "A product was missing its title.",
            retailer_id=retailer_id,
        )
    return title.strip()


def to_availability_status(base: dict[str, Any]) -> AvailabilityStatus:
    stock = base.get("inStock")
    if stock is True:
        return AvailabilityStatus.IN_STOCK
    if stock is False:
        return AvailabilityStatus.OUT_OF_STOCK
    return AvailabilityStatus.UNKNOWN


def to_attributes(base: dict[str, Any]) -> dict[str, str]:
    raw = base.get("attributes")
    attributes: dict[str, str] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
                attributes[key.strip()] = value.strip()
    for label in ("color", "size", "storage", "displaySize"):
        value = base.get(label)
        if isinstance(value, str) and value.strip():
            attributes.setdefault(label, value.strip())
    return attributes


def to_seller(shipping: dict[str, Any]) -> SellerInformation | None:
    name = shipping.get("sellerName")
    if not isinstance(name, str) or not name.strip():
        return None
    stripped = name.strip()
    return SellerInformation(
        name=stripped,
        retailer_seller_id=None,
        is_first_party=stripped.casefold() in _FIRST_PARTY_SELLERS,
    )


def source_url(base: dict[str, Any]) -> str | None:
    url = base.get("productUrl")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def displayed_price(base: dict[str, Any], *, retailer_id: str) -> tuple[Decimal, str]:
    for field in ("flipkartSellingPrice", "sellingPrice", "flipkartSpecialPrice"):
        node = base.get(field)
        amount = _inr_amount(node, retailer_id=retailer_id, field_name=field)
        if amount is None:
            continue
        currency = "INR"
        if isinstance(node, dict) and node.get("currency"):
            currency = str(node["currency"]).strip().upper() or "INR"
        return amount, currency
    raise InvalidRetailerResponseError(
        "A product did not include a displayed selling price.",
        retailer_id=retailer_id,
    )


def to_price_observation(
    payload: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> PriceObservation:
    base, shipping = _base_and_shipping(payload, retailer_id=retailer_id)
    sku = product_id(base, retailer_id=retailer_id)
    displayed, currency = displayed_price(base, retailer_id=retailer_id)
    mrp = _inr_amount(
        base.get("maximumRetailPrice"), retailer_id=retailer_id, field_name="maximumRetailPrice"
    )
    delivery = _inr_amount(
        shipping.get("shippingCharges"), retailer_id=retailer_id, field_name="shippingCharges"
    )
    return PriceObservation(
        retailer_id=retailer_id,
        retailer_sku=sku,
        observed_at=observed_at,
        currency=currency,
        displayed_price=displayed,
        mrp=mrp,
        delivery_fee=delivery,
        availability=to_availability_status(base),
        source_type=_SOURCE_TYPE,
        source_url=source_url(base),
        confidence=_CONFIDENCE,
        seller=to_seller(shipping),
    )


def to_availability_observation(
    payload: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> AvailabilityObservation:
    base, shipping = _base_and_shipping(payload, retailer_id=retailer_id)
    sku = product_id(base, retailer_id=retailer_id)
    return AvailabilityObservation(
        retailer_id=retailer_id,
        retailer_sku=sku,
        status=to_availability_status(base),
        observed_at=observed_at,
        source_type=_SOURCE_TYPE,
        source_url=source_url(base),
        confidence=_CONFIDENCE,
        seller=to_seller(shipping),
    )


def to_retailer_product(
    payload: dict[str, Any], *, retailer_id: str, retrieved_at: datetime
) -> RetailerProduct:
    base, shipping = _base_and_shipping(payload, retailer_id=retailer_id)
    sku = product_id(base, retailer_id=retailer_id)
    brand = base.get("productBrand")
    brand_name = brand.strip() if isinstance(brand, str) and brand.strip() else None
    try:
        price = to_price_observation(payload, retailer_id=retailer_id, observed_at=retrieved_at)
    except InvalidRetailerResponseError:
        price = None
    return RetailerProduct(
        retailer_id=retailer_id,
        retailer_sku=sku,
        title=product_title(base, retailer_id=retailer_id),
        url=source_url(base),
        brand_name=brand_name,
        category_path=parse_category_path(base.get("categoryPath")),
        attributes=to_attributes(base),
        seller=to_seller(shipping),
        price=price,
        availability=to_availability_observation(
            payload, retailer_id=retailer_id, observed_at=retrieved_at
        ),
        source_type=_SOURCE_TYPE,
        retrieved_at=retrieved_at,
    )
