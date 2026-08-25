"""Native payload -> standardized model mapping for MockRetailerA.

This is the only module that understands MockRetailerA's field names, its paise amounts, and its
stock vocabulary. Nothing downstream of the adapter sees any of it.
"""

from datetime import datetime
from decimal import Decimal
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
from app.retailer_adapters.mock_retailer_a.fixtures import BASE_URL

#: This retailer reports stock with its own vocabulary; map it onto the domain enum.
_STOCK_STATES: dict[str, AvailabilityStatus] = {
    "IN_STOCK": AvailabilityStatus.IN_STOCK,
    "LIMITED": AvailabilityStatus.LIMITED_STOCK,
    "OUT_OF_STOCK": AvailabilityStatus.OUT_OF_STOCK,
}

#: Data comes from an official API on request, so it is as fresh as the call itself.
_CONFIDENCE = ConfidenceLevel.HIGH
_SOURCE_TYPE = SourceType.OFFICIAL_API


def listing_url(sku: str) -> str:
    return f"{BASE_URL}/product/{sku}"


def _paise_to_rupees(value: Any, *, retailer_id: str, field_name: str) -> Decimal:
    """Convert this retailer's integer paise amounts into rupees."""
    if not isinstance(value, int):
        raise InvalidRetailerResponseError(
            f"Expected an integer paise amount for {field_name}.", retailer_id=retailer_id
        )
    return (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"))


def _availability(payload: dict[str, Any], *, retailer_id: str) -> AvailabilityStatus:
    stock = payload.get("stock")
    if stock not in _STOCK_STATES:
        raise InvalidRetailerResponseError(
            "Listing carried an unrecognized stock state.", retailer_id=retailer_id
        )
    return _STOCK_STATES[stock]


def to_seller(payload: dict[str, Any]) -> SellerInformation:
    fulfilment = payload.get("fulfilledBy") or {}
    return SellerInformation(
        name=str(fulfilment.get("name", "")),
        retailer_seller_id=fulfilment.get("id"),
        is_first_party=bool(fulfilment.get("firstParty", False)),
    )


def to_identifiers(payload: dict[str, Any]) -> tuple[ProductIdentifierValue, ...]:
    """This retailer's API exposes a GTIN per listing."""
    gtin = payload.get("gtin")
    if not gtin:
        return ()
    return (ProductIdentifierValue(identifier_type=ProductIdentifierType.GTIN, value=str(gtin)),)


def to_price_observation(
    payload: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> PriceObservation:
    """Map a listing to a price observation.

    `effective_price` is left unset: this API exposes a selling price and an MRP, not a verified
    final payable amount, and calculating one is the pricing engine's job in a later phase.
    """
    sku = str(payload["sku"])
    return PriceObservation(
        retailer_id=retailer_id,
        retailer_sku=sku,
        observed_at=observed_at,
        currency="INR",
        displayed_price=_paise_to_rupees(
            payload.get("sellingPriceInPaise"),
            retailer_id=retailer_id,
            field_name="sellingPriceInPaise",
        ),
        mrp=_paise_to_rupees(
            payload.get("listPriceInPaise"), retailer_id=retailer_id, field_name="listPriceInPaise"
        ),
        availability=_availability(payload, retailer_id=retailer_id),
        source_type=_SOURCE_TYPE,
        source_url=listing_url(sku),
        confidence=_CONFIDENCE,
        seller=to_seller(payload),
    )


def to_availability_observation(
    payload: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> AvailabilityObservation:
    sku = str(payload["sku"])
    return AvailabilityObservation(
        retailer_id=retailer_id,
        retailer_sku=sku,
        status=_availability(payload, retailer_id=retailer_id),
        observed_at=observed_at,
        source_type=_SOURCE_TYPE,
        source_url=listing_url(sku),
        confidence=_CONFIDENCE,
        seller=to_seller(payload),
    )


def to_retailer_product(
    payload: dict[str, Any], *, retailer_id: str, retrieved_at: datetime
) -> RetailerProduct:
    sku = str(payload["sku"])
    return RetailerProduct(
        retailer_id=retailer_id,
        retailer_sku=sku,
        title=str(payload["productName"]),
        url=listing_url(sku),
        brand_name=payload.get("brand"),
        category_path=tuple(payload.get("categoryPath", ())),
        attributes=dict(payload.get("attributes", {})),
        identifiers=to_identifiers(payload),
        seller=to_seller(payload),
        price=to_price_observation(payload, retailer_id=retailer_id, observed_at=retrieved_at),
        availability=to_availability_observation(
            payload, retailer_id=retailer_id, observed_at=retrieved_at
        ),
        source_type=_SOURCE_TYPE,
        retrieved_at=retrieved_at,
    )
