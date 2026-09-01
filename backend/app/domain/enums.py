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


class SaleEventType(StrEnum):
    """Kind of sale event. Generic and retailer-agnostic; no named campaigns are hardcoded.

    `manually_curated` and `externally_sourced` cover ingestion paths that do not otherwise
    fit a more specific kind. A curated retailer sale should use `retailer_specific` with
    `source=manual_curation` rather than collapsing the two dimensions.
    """

    RETAILER_SPECIFIC = "retailer_specific"
    BRAND = "brand"
    CATEGORY = "category"
    SEASONAL = "seasonal"
    NATIONAL_SHOPPING = "national_shopping"
    MANUALLY_CURATED = "manually_curated"
    EXTERNALLY_SOURCED = "externally_sourced"


class SaleEventSource(StrEnum):
    """How a `SaleEvent` record was obtained.

    External values are the same permitted acquisition methods as `SourceType`.
    `observed_price_inference` is a *calculated* detection from stored price observations,
    never an observed retailer-published event name.
    """

    MANUAL_CURATION = "manual_curation"
    OFFICIAL_API = "official_api"
    AFFILIATE_FEED = "affiliate_feed"
    PRODUCT_FEED = "product_feed"
    OTHER_PERMITTED = "other_permitted"
    OBSERVED_PRICE_INFERENCE = "observed_price_inference"


class SaleEventStatus(StrEnum):
    """Lifecycle of a sale event relative to a point in time.

    Derived from `start_date`/`end_date`; not stored. Inclusive of both bounds for
    `during_event`.
    """

    BEFORE_EVENT = "before_event"
    DURING_EVENT = "during_event"
    AFTER_EVENT = "after_event"


class SaleSeverity(StrEnum):
    """Evidence-based sale magnitude. Not a named campaign list.

    Derived at analysis time from duration, recurrence, discount magnitude, and event
    type. Never inferred from a hardcoded real-world sale name.
    """

    MAJOR = "MAJOR"
    ORDINARY = "ORDINARY"
    UNKNOWN = "UNKNOWN"


class SaleEvidenceStatus(StrEnum):
    """How strongly a future sale window is supported.

    `confirmed` requires a persisted event from curation or a permitted source whose
    dates are already on the record. Historical mapping is `expected` or `inferred`.
    Insufficient evidence is `unknown`. Projected dates are never guaranteed offers.
    """

    CONFIRMED = "confirmed"
    EXPECTED = "expected"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class SaleMappingMethod(StrEnum):
    """How a current-year expected window was derived from historical events."""

    FIXED_CALENDAR = "fixed_calendar"
    FESTIVAL_RELATIVE = "festival_relative"
    RECURRING = "recurring"
    RETAILER_SPECIFIC = "retailer_specific"
    CONFIRMED_SCHEDULE = "confirmed_schedule"
    INSUFFICIENT = "insufficient"


class CollectionJobType(StrEnum):
    """Logical background collection job kinds (Phase 13)."""

    PRODUCT_SEARCH = "product_search"
    PRODUCT_REFRESH = "product_refresh"
    PRICE_REFRESH = "price_refresh"
    AVAILABILITY_REFRESH = "availability_refresh"
    SALE_EVENT_REFRESH = "sale_event_refresh"


class CollectionJobStatus(StrEnum):
    """Persistent lifecycle of one `CollectionJob` row."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class CollectionErrorCategory(StrEnum):
    """Retailer-agnostic classification of a collection failure.

    Permanent/validation categories are not retried. Transient categories may be retried
    under the collection retry policy until attempts are exhausted.
    """

    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    TEMPORARY_FAILURE = "temporary_failure"
    VALIDATION = "validation"
    PERMANENT = "permanent"
    CONFIGURATION = "configuration"
    UNEXPECTED = "unexpected"
