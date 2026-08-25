"""Native feed row -> standardized model mapping for MockRetailerB.

Everything specific to this retailer lives here: string amounts, `Y`/`L`/`N` stock flags, the
`key=value|key=value` spec encoding, and its `>`-delimited category string.
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
    PriceObservation,
    ProductIdentifierValue,
    RetailerProduct,
    SellerInformation,
)
from app.retailer_adapters.mock_retailer_b.fixtures import BASE_URL

_STOCK_FLAGS: dict[str, AvailabilityStatus] = {
    "Y": AvailabilityStatus.IN_STOCK,
    "L": AvailabilityStatus.LIMITED_STOCK,
    "N": AvailabilityStatus.OUT_OF_STOCK,
}

#: An affiliate feed is refreshed periodically rather than read live, so observations from it are
#: inherently less fresh than an on-request API call.
_CONFIDENCE = ConfidenceLevel.MEDIUM
_SOURCE_TYPE = SourceType.AFFILIATE_FEED


def listing_url(item_id: str) -> str:
    return f"{BASE_URL}/i/{item_id}"


def _amount(raw: Any, *, retailer_id: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, ArithmeticError, TypeError) as exc:
        raise InvalidRetailerResponseError(
            f"Feed row carried a non-numeric amount for {field_name}.", retailer_id=retailer_id
        ) from exc


def parse_specs(raw: str) -> dict[str, str]:
    """Decode this feed's `key=value|key=value` spec string into a mapping."""
    specs: dict[str, str] = {}
    for part in str(raw).split("|"):
        if not part.strip():
            continue
        key, separator, value = part.partition("=")
        if not separator:
            continue
        specs[key.strip()] = value.strip()
    return specs


def _availability(row: dict[str, Any], *, retailer_id: str) -> AvailabilityStatus:
    flag = str(row.get("stock", "")).upper()
    if flag not in _STOCK_FLAGS:
        raise InvalidRetailerResponseError(
            "Feed row carried an unrecognized stock flag.", retailer_id=retailer_id
        )
    return _STOCK_FLAGS[flag]


def to_seller(row: dict[str, Any]) -> SellerInformation:
    """Listings on this marketplace are fulfilled by third-party sellers, never the retailer."""
    return SellerInformation(
        name=str(row.get("seller_name", "")),
        retailer_seller_id=row.get("seller_code"),
        is_first_party=False,
    )


def to_identifiers(row: dict[str, Any]) -> tuple[ProductIdentifierValue, ...]:
    """This feed exposes a manufacturer part number, but no GTIN/EAN/UPC."""
    mpn = row.get("mpn")
    if not mpn:
        return ()
    return (ProductIdentifierValue(identifier_type=ProductIdentifierType.MPN, value=str(mpn)),)


def to_price_observation(
    row: dict[str, Any], *, retailer_id: str, observed_at: datetime
) -> PriceObservation:
    """Map a feed row to a price observation.

    This feed publishes `final_payable` alongside the item price, so `effective_price` is set
    from a value the source itself provided. It is never derived here — an adapter reports what
    it was given, and calculating an effective price is the pricing engine's job.
    """
    item_id = str(row["item_id"])
    return PriceObservation(
        retailer_id=retailer_id,
        retailer_sku=item_id,
        observed_at=observed_at,
        currency="INR",
        displayed_price=_amount(row.get("price"), retailer_id=retailer_id, field_name="price"),
        mrp=_amount(row.get("mrp"), retailer_id=retailer_id, field_name="mrp"),
        effective_price=_amount(
            row.get("final_payable"), retailer_id=retailer_id, field_name="final_payable"
        ),
        delivery_fee=_amount(row.get("delivery"), retailer_id=retailer_id, field_name="delivery"),
        availability=_availability(row, retailer_id=retailer_id),
        source_type=_SOURCE_TYPE,
        source_url=listing_url(item_id),
        confidence=_CONFIDENCE,
        seller=to_seller(row),
    )


def to_retailer_product(
    row: dict[str, Any], *, retailer_id: str, retrieved_at: datetime
) -> RetailerProduct:
    """Map a feed row to a standardized listing.

    `availability` is left unset: this feed only reports stock as part of a priced row, and this
    retailer exposes no standalone availability lookup (its adapter does not declare
    `get_availability`).
    """
    item_id = str(row["item_id"])
    return RetailerProduct(
        retailer_id=retailer_id,
        retailer_sku=item_id,
        title=str(row["name"]),
        url=listing_url(item_id),
        brand_name=row.get("mfr"),
        category_path=tuple(
            segment.strip() for segment in str(row.get("cat", "")).split(">") if segment.strip()
        ),
        attributes=parse_specs(row.get("specs", "")),
        identifiers=to_identifiers(row),
        seller=to_seller(row),
        price=to_price_observation(row, retailer_id=retailer_id, observed_at=retrieved_at),
        source_type=_SOURCE_TYPE,
        retrieved_at=retrieved_at,
    )
