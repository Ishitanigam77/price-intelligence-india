"""Native feed entry -> standardized model mapping for MockRetailerC.

Retailer-specific concerns handled here: `*_inr` string amounts, word stock states, the nested
`variant` block, and the fact that this retailer is its own (first-party) seller.
"""

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
from app.retailer_adapters.mock_retailer_c.fixtures import BASE_URL

_STOCK_STATES: dict[str, AvailabilityStatus] = {
    "in_stock": AvailabilityStatus.IN_STOCK,
    "limited": AvailabilityStatus.LIMITED_STOCK,
    "sold_out": AvailabilityStatus.OUT_OF_STOCK,
    "unknown": AvailabilityStatus.UNKNOWN,
}

#: A nightly feed can be up to a day stale, which is a materially weaker guarantee than an
#: on-request API call — recorded honestly rather than optimistically.
_CONFIDENCE = ConfidenceLevel.LOW
_SOURCE_TYPE = SourceType.PRODUCT_FEED

#: This is a first-party store: the retailer fulfils its own listings.
_SELLER_NAME = "Fictional Mock Depot C"


def listing_url(item_code: str) -> str:
    return f"{BASE_URL}/catalogue/{item_code.replace('/', '-').lower()}"


def _amount(raw: Any, *, retailer_id: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, ArithmeticError, TypeError) as exc:
        raise InvalidRetailerResponseError(
            f"Feed entry carried a non-numeric amount for {field_name}.", retailer_id=retailer_id
        ) from exc


def _availability(entry: dict[str, Any], *, retailer_id: str) -> AvailabilityStatus:
    state = str(entry.get("stock_state", "")).lower()
    if state not in _STOCK_STATES:
        raise InvalidRetailerResponseError(
            "Feed entry carried an unrecognized stock state.", retailer_id=retailer_id
        )
    return _STOCK_STATES[state]


def to_seller(retailer_id: str) -> SellerInformation:
    return SellerInformation(name=_SELLER_NAME, retailer_seller_id=retailer_id, is_first_party=True)


def to_price_observation(
    entry: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> PriceObservation:
    """Map a feed entry to a price observation.

    `effective_price` stays unset: this feed publishes an offer price and a platform fee but no
    verified final payable amount, so combining them would be a calculation this layer must not
    make.
    """
    item_code = str(entry["item_code"])
    return PriceObservation(
        retailer_id=retailer_id,
        retailer_sku=item_code,
        observed_at=observed_at,
        currency="INR",
        displayed_price=_amount(
            entry.get("offer_inr"), retailer_id=retailer_id, field_name="offer_inr"
        ),
        mrp=_amount(entry.get("mrp_inr"), retailer_id=retailer_id, field_name="mrp_inr"),
        platform_fee=_amount(
            entry.get("platform_fee_inr"), retailer_id=retailer_id, field_name="platform_fee_inr"
        ),
        availability=_availability(entry, retailer_id=retailer_id),
        source_type=_SOURCE_TYPE,
        source_url=listing_url(item_code),
        confidence=_CONFIDENCE,
        seller=to_seller(retailer_id),
    )


def to_availability_observation(
    entry: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> AvailabilityObservation:
    item_code = str(entry["item_code"])
    return AvailabilityObservation(
        retailer_id=retailer_id,
        retailer_sku=item_code,
        status=_availability(entry, retailer_id=retailer_id),
        observed_at=observed_at,
        source_type=_SOURCE_TYPE,
        source_url=listing_url(item_code),
        confidence=_CONFIDENCE,
        seller=to_seller(retailer_id),
    )


def to_retailer_product(
    entry: dict[str, Any], *, retailer_id: str, retrieved_at: datetime
) -> RetailerProduct:
    """Map a feed entry to a standardized listing.

    `identifiers` is empty: this feed publishes no GTIN/EAN/UPC/MPN, and inventing one would be
    fabricating data. Cross-retailer matching for this retailer has to rely on other signals.
    """
    item_code = str(entry["item_code"])
    return RetailerProduct(
        retailer_id=retailer_id,
        retailer_sku=item_code,
        title=str(entry["title"]),
        url=listing_url(item_code),
        brand_name=entry.get("manufacturer"),
        category_path=(str(entry["department"]),) if entry.get("department") else (),
        attributes={str(key): str(value) for key, value in (entry.get("variant") or {}).items()},
        identifiers=(),
        seller=to_seller(retailer_id),
        price=to_price_observation(entry, retailer_id=retailer_id, observed_at=retrieved_at),
        availability=to_availability_observation(
            entry, retailer_id=retailer_id, observed_at=retrieved_at
        ),
        source_type=_SOURCE_TYPE,
        retrieved_at=retrieved_at,
    )
