"""Standardized models exchanged across the adapter boundary.

These models *are* the boundary described in `RETAILER_ARCHITECTURE.md` §3:

    retailer-specific data      native JSON / CSV / XML payloads, retailer field names
            |                   (never leaves the adapter package)
            v
    retailer adapter            <retailer>/mapping.py translates native -> standardized
            |
            v
    standardized retailer       RetailerProduct, PriceObservation, AvailabilityObservation,
    models                      SellerInformation: still in the *retailer's* vocabulary
            |                   (its own SKU, title, taxonomy) but in a fixed shape
            v
    NormalizedProduct           retailer-agnostic shape: normalized variant attributes and a
            |                   deterministic variant key, ready for core consumption
            v
    core application/domain     matching, pricing, comparison — sees only these models

Everything here is an immutable Pydantic model validated with the Phase 1 domain validators
(`app.domain.validation`) and the Phase 1 enums (`app.domain.enums`), so an adapter physically
cannot hand the core a negative price, a malformed currency code, or a naive timestamp.

Note on naming: `RetailerProduct` here is the *in-flight* standardized payload an adapter
returns. It is not the Phase 1 ORM entity `app.db.models.RetailerProduct` (the persisted
retailer listing). Adapters never touch the ORM; persisting these payloads is the job of later
phases, which is why the two can share a name without ambiguity in practice — the adapter layer
only ever imports this one.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    ProductIdentifierType,
    SourceType,
)
from app.domain.validation import (
    build_variant_key,
    normalize_variant_attributes,
    validate_currency_code,
    validate_non_negative_amount,
    validate_required_non_negative_amount,
    validate_slug,
)
from app.retailer_adapters.base.errors import AdapterErrorCode


class HealthStatus(StrEnum):
    """Operational health of an adapter, as reported by its last health check."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


def _require_aware(value: datetime, *, field_name: str) -> datetime:
    """Reject naive timestamps: an observation time without a timezone is not a fact."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    return value


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProductIdentifierValue(_FrozenModel):
    """A cross-retailer product identifier (GTIN/EAN/UPC/ISBN/MPN) as exposed by a retailer.

    Retailer-native listing ids (an internal SKU) are *not* identifiers in this sense — those
    live on `retailer_sku`. Reuses the Phase 1 `ProductIdentifierType` enum.
    """

    identifier_type: ProductIdentifierType
    value: str = Field(min_length=1, max_length=200)

    @field_validator("value")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Identifier value must not be blank.")
        return stripped


class SellerInformation(_FrozenModel):
    """The seller fulfilling a listing.

    On a marketplace this is a third party; on a first-party retailer it is the retailer itself
    (`is_first_party=True`). Mirrors the Phase 1 `Seller` entity's shape without depending on it.
    """

    name: str = Field(min_length=1, max_length=200)
    #: The seller's identifier in the retailer's own namespace, when the source exposes one.
    retailer_seller_id: str | None = Field(default=None, max_length=200)
    is_first_party: bool = False


class PriceObservation(_FrozenModel):
    """One immutable, timestamped price observation, in the shape the core domain consumes.

    Carries every field required by `RETAILER_ARCHITECTURE.md` §6 (retailer, seller, source URL,
    observation timestamp, displayed price, MRP, effective price, availability, source type,
    confidence) so provenance is never lost between the adapter and storage.

    `effective_price` stays `None` unless the source itself provided a verified final payable
    amount. Deriving it from discounts/fees is a *calculation*, owned by the pricing engine in a
    later phase; an adapter must never guess it.
    """

    retailer_id: str
    retailer_sku: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    currency: str = "INR"
    displayed_price: Decimal
    mrp: Decimal | None = None
    effective_price: Decimal | None = None
    delivery_fee: Decimal | None = None
    platform_fee: Decimal | None = None
    availability: AvailabilityStatus
    source_type: SourceType
    source_url: str | None = None
    confidence: ConfidenceLevel
    seller: SellerInformation | None = None

    @field_validator("retailer_id")
    @classmethod
    def _validate_retailer_id(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("observed_at")
    @classmethod
    def _validate_observed_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="observed_at")

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)

    @field_validator("displayed_price")
    @classmethod
    def _validate_displayed_price(cls, value: Decimal) -> Decimal:
        return validate_required_non_negative_amount(value, field_name="displayed_price")

    @field_validator("mrp", "effective_price", "delivery_fee", "platform_fee")
    @classmethod
    def _validate_optional_amount(cls, value: Decimal | None) -> Decimal | None:
        return validate_non_negative_amount(value, field_name="amount")


class AvailabilityObservation(_FrozenModel):
    """One immutable, timestamped availability observation for a retailer listing.

    Separate from `PriceObservation` because several legitimate sources expose stock state on a
    different endpoint/feed (and on a different cadence) than price.
    """

    retailer_id: str
    retailer_sku: str = Field(min_length=1, max_length=200)
    status: AvailabilityStatus
    observed_at: datetime
    source_type: SourceType
    source_url: str | None = None
    confidence: ConfidenceLevel
    seller: SellerInformation | None = None

    @field_validator("retailer_id")
    @classmethod
    def _validate_retailer_id(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("observed_at")
    @classmethod
    def _validate_observed_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="observed_at")


class RetailerProduct(_FrozenModel):
    """A listing as the retailer describes it, in a standardized shape.

    Field *names* are standardized; field *values* are still the retailer's own vocabulary — its
    SKU, its product title, its category path, its attribute labels. Nothing here has been
    matched to a `Product`/`ProductVariant` yet, and nothing retailer-native (raw payloads,
    endpoints, vendor codes) is carried through.
    """

    retailer_id: str
    retailer_sku: str = Field(min_length=1, max_length=200)
    #: The product title exactly as the retailer presents it.
    title: str = Field(min_length=1, max_length=1000)
    url: str | None = None
    brand_name: str | None = Field(default=None, max_length=200)
    #: The retailer's own category path, outermost first, e.g. ("Electronics", "Mobiles").
    category_path: tuple[str, ...] = ()
    #: The retailer's own attribute labels and values, e.g. {"Storage": "128 GB"}.
    attributes: Mapping[str, str] = Field(default_factory=dict)
    identifiers: tuple[ProductIdentifierValue, ...] = ()
    seller: SellerInformation | None = None
    #: Price/availability as of this fetch, when the same response carried them.
    price: PriceObservation | None = None
    availability: AvailabilityObservation | None = None
    source_type: SourceType
    retrieved_at: datetime

    @field_validator("retailer_id")
    @classmethod
    def _validate_retailer_id(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("retrieved_at")
    @classmethod
    def _validate_retrieved_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="retrieved_at")

    @model_validator(mode="after")
    def _validate_embedded_observations(self) -> "RetailerProduct":
        for label, observation in (("price", self.price), ("availability", self.availability)):
            if observation is None:
                continue
            if observation.retailer_id != self.retailer_id:
                raise ValueError(f"{label}.retailer_id must match the product's retailer_id.")
            if observation.retailer_sku != self.retailer_sku:
                raise ValueError(f"{label}.retailer_sku must match the product's retailer_sku.")
        return self


class NormalizedProduct(_FrozenModel):
    """A retailer listing reduced to the retailer-agnostic shape the core domain consumes.

    Produced by `RetailerAdapter.normalize_product`, whose job is *structural*: map this
    retailer's vocabulary onto common fields. Deeper normalization (unit/text cleaning, brand
    extraction, taxonomy mapping) and any matching decision belong to `app/normalization/` and
    `app/matching/` in a later phase — an adapter must not attempt them.

    `variant_attributes` is normalized with the Phase 1 helper, and `variant_key` is derived
    with the same deterministic function the ORM uses, so two retailers describing the same
    configuration produce the same key.
    """

    retailer_id: str
    retailer_sku: str = Field(min_length=1, max_length=200)
    #: Title with surrounding whitespace collapsed; still the retailer's wording.
    normalized_title: str = Field(min_length=1, max_length=1000)
    brand_name: str | None = Field(default=None, max_length=200)
    brand_slug: str | None = None
    category_slug: str | None = None
    variant_attributes: Mapping[str, str]
    identifiers: tuple[ProductIdentifierValue, ...] = ()
    source_url: str | None = None
    source_type: SourceType
    normalized_at: datetime

    @field_validator("retailer_id")
    @classmethod
    def _validate_retailer_id(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("brand_slug", "category_slug")
    @classmethod
    def _validate_optional_slug(cls, value: str | None) -> str | None:
        return None if value is None else validate_slug(value)

    @field_validator("variant_attributes")
    @classmethod
    def _normalize_attributes(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return normalize_variant_attributes(dict(value))

    @field_validator("normalized_at")
    @classmethod
    def _validate_normalized_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="normalized_at")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def variant_key(self) -> str:
        """Deterministic key for this variant configuration (same derivation as Phase 1's ORM)."""
        return build_variant_key(dict(self.variant_attributes))


class ProductSearchQuery(_FrozenModel):
    """A retailer-agnostic product discovery request."""

    text: str | None = Field(default=None, max_length=500)
    #: Category slug to scope the search to, matched against `supported_categories`.
    category: str | None = None
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str | None) -> str | None:
        return None if value is None else validate_slug(value)

    @model_validator(mode="after")
    def _require_a_criterion(self) -> "ProductSearchQuery":
        if not (self.text and self.text.strip()) and self.category is None:
            raise ValueError("A search query needs free text, a category, or both.")
        return self


class ProductSearchResult(_FrozenModel):
    """What one adapter returned for one search query."""

    retailer_id: str
    query: ProductSearchQuery
    products: tuple[RetailerProduct, ...] = ()
    retrieved_at: datetime

    @field_validator("retailer_id")
    @classmethod
    def _validate_retailer_id(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("retrieved_at")
    @classmethod
    def _validate_retrieved_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="retrieved_at")


class HealthCheckResult(_FrozenModel):
    """Outcome of one adapter health check, feeding retailer health/freshness features later."""

    retailer_id: str
    status: HealthStatus
    checked_at: datetime
    duration_ms: float = Field(ge=0.0)
    #: Short, retailer-agnostic explanation when not healthy.
    detail: str | None = Field(default=None, max_length=500)
    error_code: AdapterErrorCode | None = None

    @field_validator("retailer_id")
    @classmethod
    def _validate_retailer_id(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("checked_at")
    @classmethod
    def _validate_checked_at(cls, value: datetime) -> datetime:
        return _require_aware(value, field_name="checked_at")

    @property
    def is_healthy(self) -> bool:
        return self.status is HealthStatus.HEALTHY
