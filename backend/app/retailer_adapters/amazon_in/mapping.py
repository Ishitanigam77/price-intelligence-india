"""Native Creators API payload → standardized models for Amazon.in.

This is the only module that understands Creators API field names (`offersV2`, `itemInfo`,
`displayValue`, ASIN). Nothing downstream of the adapter sees them.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    ProductIdentifierType,
    SourceType,
)
from app.retailer_adapters.base.errors import InvalidRetailerResponseError
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    PriceObservation,
    ProductIdentifierValue,
    RetailerProduct,
    SellerInformation,
)

_SOURCE_TYPE = SourceType.AFFILIATE_FEED
_CONFIDENCE = ConfidenceLevel.HIGH

_AVAILABILITY_BY_TYPE: dict[str, AvailabilityStatus] = {
    "IN_STOCK": AvailabilityStatus.IN_STOCK,
    "INSTOCK": AvailabilityStatus.IN_STOCK,
    "NOW": AvailabilityStatus.IN_STOCK,
    "AVAILABLE": AvailabilityStatus.IN_STOCK,
    "OUT_OF_STOCK": AvailabilityStatus.OUT_OF_STOCK,
    "OUTOFSTOCK": AvailabilityStatus.OUT_OF_STOCK,
    "UNAVAILABLE": AvailabilityStatus.OUT_OF_STOCK,
    "LIMITED": AvailabilityStatus.LIMITED_STOCK,
    "LOW_STOCK": AvailabilityStatus.LIMITED_STOCK,
    "LIMITED_STOCK": AvailabilityStatus.LIMITED_STOCK,
}

_FIRST_PARTY_SELLER_PREFIXES = ("amazon",)


def display_value(node: Any) -> str | None:
    """Read a Creators API `displayValue` wrapper, or a plain string."""
    if node is None:
        return None
    if isinstance(node, str):
        stripped = node.strip()
        return stripped or None
    if isinstance(node, dict):
        raw = node.get("displayValue")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _decimal_amount(value: Any, *, retailer_id: str, field_name: str) -> Decimal:
    try:
        amount = Decimal(str(value))
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


def money_amount(
    node: Any, *, retailer_id: str, field_name: str
) -> tuple[Decimal, str] | None:
    """Extract `(amount, currency)` from an `offersV2` money object."""
    if node is None:
        return None
    if not isinstance(node, dict):
        raise InvalidRetailerResponseError(
            f"Expected a money object for {field_name}.",
            retailer_id=retailer_id,
        )
    money = node.get("money") if isinstance(node.get("money"), dict) else node
    if not isinstance(money, dict):
        return None
    if money.get("amount") is None:
        return None
    currency = str(money.get("currency") or "INR").strip().upper() or "INR"
    amount = _decimal_amount(money["amount"], retailer_id=retailer_id, field_name=field_name)
    return amount, currency


def items_from_payload(payload: dict[str, Any], *, retailer_id: str) -> list[dict[str, Any]]:
    """Locate the items array on SearchItems or GetItems responses."""
    for key in ("searchResult", "itemResults", "itemsResult"):
        container = payload.get(key)
        if isinstance(container, dict) and isinstance(container.get("items"), list):
            return [item for item in container["items"] if isinstance(item, dict)]
    if isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    raise InvalidRetailerResponseError(
        "Creators API response did not contain an items list.",
        retailer_id=retailer_id,
    )


def item_asin(item: dict[str, Any], *, retailer_id: str) -> str:
    asin = item.get("asin")
    if not isinstance(asin, str) or not asin.strip():
        raise InvalidRetailerResponseError(
            "An item was missing its ASIN.",
            retailer_id=retailer_id,
        )
    return asin.strip()


def item_title(item: dict[str, Any], *, retailer_id: str) -> str:
    info = item.get("itemInfo") if isinstance(item.get("itemInfo"), dict) else {}
    title = display_value(info.get("title")) if isinstance(info, dict) else None
    if not title:
        raise InvalidRetailerResponseError(
            "An item was missing its title.",
            retailer_id=retailer_id,
        )
    return title


def _buy_box_listing(item: dict[str, Any]) -> dict[str, Any] | None:
    offers = item.get("offersV2")
    if not isinstance(offers, dict):
        return None
    listings = offers.get("listings")
    if not isinstance(listings, list) or not listings:
        return None
    typed = [entry for entry in listings if isinstance(entry, dict)]
    for listing in typed:
        if listing.get("isBuyBoxWinner") is True:
            return listing
    return typed[0]


def to_seller(item: dict[str, Any]) -> SellerInformation | None:
    listing = _buy_box_listing(item)
    if listing is None:
        return None
    merchant = listing.get("merchantInfo")
    if not isinstance(merchant, dict):
        return None
    name = merchant.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    seller_id = merchant.get("id")
    lowered = name.strip().casefold()
    is_first_party = any(
        lowered == prefix or lowered.startswith(f"{prefix}.") or lowered.startswith(f"{prefix} ")
        for prefix in _FIRST_PARTY_SELLER_PREFIXES
    )
    return SellerInformation(
        name=name.strip(),
        retailer_seller_id=str(seller_id).strip() if seller_id else None,
        is_first_party=is_first_party,
    )


def to_availability_status(item: dict[str, Any]) -> AvailabilityStatus:
    listing = _buy_box_listing(item)
    if listing is None:
        return AvailabilityStatus.UNKNOWN
    availability = listing.get("availability")
    if not isinstance(availability, dict):
        return AvailabilityStatus.UNKNOWN
    raw = availability.get("type")
    if not isinstance(raw, str) or not raw.strip():
        return AvailabilityStatus.UNKNOWN
    key = raw.strip().upper().replace(" ", "_")
    return _AVAILABILITY_BY_TYPE.get(key, AvailabilityStatus.UNKNOWN)


def to_identifiers(item: dict[str, Any]) -> tuple[ProductIdentifierValue, ...]:
    info = item.get("itemInfo") if isinstance(item.get("itemInfo"), dict) else {}
    if not isinstance(info, dict):
        return ()
    external = info.get("externalIds")
    if not isinstance(external, dict):
        return ()
    collected: list[ProductIdentifierValue] = []
    mapping = (
        (("eaNs", "EANs", "eans"), ProductIdentifierType.EAN),
        (("upCs", "UPCs", "upcs"), ProductIdentifierType.UPC),
        (("isbNs", "ISBNs", "isbns"), ProductIdentifierType.ISBN),
        (("gtins", "GTINs", "gtIns"), ProductIdentifierType.GTIN),
    )
    seen: set[tuple[str, str]] = set()
    for keys, identifier_type in mapping:
        block = None
        for key in keys:
            if key in external and isinstance(external[key], dict):
                block = external[key]
                break
        if block is None:
            continue
        values = block.get("displayValues")
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            stripped = value.strip()
            fingerprint = (identifier_type.value, stripped)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            collected.append(
                ProductIdentifierValue(identifier_type=identifier_type, value=stripped)
            )
    manufacture = info.get("manufactureInfo")
    if isinstance(manufacture, dict):
        part = display_value(manufacture.get("itemPartNumber"))
        if part:
            fingerprint = (ProductIdentifierType.MPN.value, part)
            if fingerprint not in seen:
                collected.append(
                    ProductIdentifierValue(identifier_type=ProductIdentifierType.MPN, value=part)
                )
    return tuple(collected)


def to_attributes(item: dict[str, Any]) -> dict[str, str]:
    attributes: dict[str, str] = {}
    variations = item.get("variationAttributes")
    if isinstance(variations, list):
        for entry in variations:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            value = entry.get("value")
            if isinstance(name, str) and name.strip() and isinstance(value, str) and value.strip():
                attributes[name.strip()] = value.strip()
    info = item.get("itemInfo") if isinstance(item.get("itemInfo"), dict) else {}
    if isinstance(info, dict):
        product_info = info.get("productInfo")
        if isinstance(product_info, dict):
            for label, key in (("color", "color"), ("size", "size")):
                value = display_value(product_info.get(key))
                if value:
                    attributes.setdefault(label, value)
    return attributes


def to_category_path(item: dict[str, Any]) -> tuple[str, ...]:
    browse = item.get("browseNodeInfo")
    names: list[str] = []
    if isinstance(browse, dict):
        nodes = browse.get("browseNodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                name = node.get("displayName")
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())
    if names:
        return tuple(names)
    info = item.get("itemInfo") if isinstance(item.get("itemInfo"), dict) else {}
    if isinstance(info, dict):
        classifications = info.get("classifications")
        if isinstance(classifications, dict):
            group = display_value(classifications.get("productGroup"))
            binding = display_value(classifications.get("binding"))
            path = tuple(part for part in (binding, group) if part)
            if path:
                return path
    return ()


def to_brand_name(item: dict[str, Any]) -> str | None:
    info = item.get("itemInfo") if isinstance(item.get("itemInfo"), dict) else {}
    if not isinstance(info, dict):
        return None
    byline = info.get("byLineInfo")
    if isinstance(byline, dict):
        return display_value(byline.get("brand"))
    return None


def source_url(item: dict[str, Any]) -> str | None:
    url = item.get("detailPageURL")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def to_price_observation(
    item: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> PriceObservation:
    sku = item_asin(item, retailer_id=retailer_id)
    listing = _buy_box_listing(item)
    if listing is None:
        raise InvalidRetailerResponseError(
            "An item did not include an offer listing with a price.",
            retailer_id=retailer_id,
        )
    priced = money_amount(listing.get("price"), retailer_id=retailer_id, field_name="price")
    if priced is None:
        raise InvalidRetailerResponseError(
            "An item did not include a displayed price.",
            retailer_id=retailer_id,
        )
    displayed, currency = priced
    mrp = None
    price_node = listing.get("price")
    if isinstance(price_node, dict):
        basis = money_amount(
            price_node.get("savingBasis"), retailer_id=retailer_id, field_name="savingBasis"
        )
        if basis is not None:
            mrp = basis[0]
    return PriceObservation(
        retailer_id=retailer_id,
        retailer_sku=sku,
        observed_at=observed_at,
        currency=currency,
        displayed_price=displayed,
        mrp=mrp,
        availability=to_availability_status(item),
        source_type=_SOURCE_TYPE,
        source_url=source_url(item),
        confidence=_CONFIDENCE,
        seller=to_seller(item),
    )


def to_availability_observation(
    item: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> AvailabilityObservation:
    sku = item_asin(item, retailer_id=retailer_id)
    return AvailabilityObservation(
        retailer_id=retailer_id,
        retailer_sku=sku,
        status=to_availability_status(item),
        observed_at=observed_at,
        source_type=_SOURCE_TYPE,
        source_url=source_url(item),
        confidence=_CONFIDENCE,
        seller=to_seller(item),
    )


def to_retailer_product(
    item: dict[str, Any], *, retailer_id: str, retrieved_at: datetime
) -> RetailerProduct:
    sku = item_asin(item, retailer_id=retailer_id)
    price = None
    listing = _buy_box_listing(item)
    if listing is not None:
        try:
            price = to_price_observation(item, retailer_id=retailer_id, observed_at=retrieved_at)
        except InvalidRetailerResponseError:
            price = None
    return RetailerProduct(
        retailer_id=retailer_id,
        retailer_sku=sku,
        title=item_title(item, retailer_id=retailer_id),
        url=source_url(item),
        brand_name=to_brand_name(item),
        category_path=to_category_path(item),
        attributes=to_attributes(item),
        identifiers=to_identifiers(item),
        seller=to_seller(item),
        price=price,
        availability=to_availability_observation(
            item, retailer_id=retailer_id, observed_at=retrieved_at
        ),
        source_type=_SOURCE_TYPE,
        retrieved_at=retrieved_at,
    )


def find_item(
    payload: dict[str, Any], *, asin: str, retailer_id: str
) -> dict[str, Any] | None:
    wanted = asin.strip().upper()
    for item in items_from_payload(payload, retailer_id=retailer_id):
        found = item.get("asin")
        if isinstance(found, str) and found.strip().upper() == wanted:
            return item
    return None
