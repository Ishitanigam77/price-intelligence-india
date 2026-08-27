"""Enumerations shared by the domain and persistence layers.

These are plain `enum.Enum` subclasses (not tied to SQLAlchemy) so they can be reused anywhere,
including in future API schemas, without pulling in the ORM.
"""

from enum import StrEnum


class AvailabilityStatus(StrEnum):
    """Availability of a retailer's listing at the moment a price was observed.

    Modeled as an attribute of a `PriceSnapshot` rather than a separate table, per
    `RETAILER_ARCHITECTURE.md` §6: every Price Observation must itself carry an availability
    value alongside price — a listing being in/out of stock is a fact tied to a single
    observation in time, not an independent long-lived entity.
    """

    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    LIMITED_STOCK = "limited_stock"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """How a Price Observation's data was legitimately obtained.

    Mirrors the `source_type` contract field defined in `RETAILER_ARCHITECTURE.md` §6. Never
    represents scraping/bypass techniques — only permitted acquisition methods.
    """

    OFFICIAL_API = "official_api"
    AFFILIATE_FEED = "affiliate_feed"
    PRODUCT_FEED = "product_feed"
    OTHER_PERMITTED = "other_permitted"


class ConfidenceLevel(StrEnum):
    """Data freshness/confidence indicator required on every Price Observation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProductIdentifierType(StrEnum):
    """Types of cross-retailer product identifiers used for future product matching.

    These are identifiers that refer to the *same real-world product variant* regardless of
    which retailer lists it (GTIN/EAN/UPC/ISBN/MPN). Retailer-specific native listing ids (e.g.
    an ASIN or FSN) are not product identifiers in this sense — they identify one retailer's
    listing, and are stored on `RetailerProduct.retailer_sku` instead.
    """

    GTIN = "gtin"
    EAN = "ean"
    UPC = "upc"
    ISBN = "isbn"
    MPN = "mpn"
    OTHER = "other"


class AdjustmentKind(StrEnum):
    """Kind of a price adjustment attached to a retailer offer.

    Promotional kinds (coupon, payment discount, cashback) may reduce the verified effective
    price only when eligibility is `verified_eligible`. Fee kinds are additive costs. Displayed
    discount is informational: it is already reflected in `displayed_price` and never applied
    a second time.
    """

    COUPON = "coupon"
    PAYMENT_DISCOUNT = "payment_discount"
    CASHBACK = "cashback"
    DELIVERY_FEE = "delivery_fee"
    PLATFORM_FEE = "platform_fee"
    DISPLAYED_DISCOUNT = "displayed_discount"
    OTHER = "other"


class AdjustmentEligibility(StrEnum):
    """Whether a price adjustment is verified as applicable to the offer being compared.

    Only `verified_eligible` adjustments may change the verified effective price. Every other
    state is preserved for provenance and must not be treated as a universal discount.
    """

    VERIFIED_ELIGIBLE = "verified_eligible"
    INELIGIBLE = "ineligible"
    UNVERIFIED = "unverified"
    UNAVAILABLE = "unavailable"
    MEMBERSHIP_ONLY = "membership_only"
    PAYMENT_METHOD_SPECIFIC = "payment_method_specific"
    CONDITIONAL = "conditional"
