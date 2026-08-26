"""Retailer-agnostic inputs and outputs of the price comparison engine.

The engine never sees ORM objects or HTTP schemas. Callers (the comparison service) project
persisted listings/snapshots into `OfferInput` values and receive `ProductComparison` back.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.domain.enums import (
    AdjustmentEligibility,
    AdjustmentKind,
    AvailabilityStatus,
    ConfidenceLevel,
    SourceType,
)
from app.domain.validation import validate_currency_code, validate_non_negative_amount
from app.pricing.enums import FreshnessStatus, PriceKind, RankingCriterion
from app.pricing.money import optional_money, quantize_money

_PROMOTIONAL_KINDS = frozenset(
    {
        AdjustmentKind.COUPON,
        AdjustmentKind.PAYMENT_DISCOUNT,
        AdjustmentKind.CASHBACK,
    }
)
_FEE_KINDS = frozenset({AdjustmentKind.DELIVERY_FEE, AdjustmentKind.PLATFORM_FEE})


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class PriceAdjustment(_FrozenModel):
    """One itemized price adjustment with full provenance.

    An adjustment may change `effective_price` only when `affects_effective_price` is true,
    which requires verified eligibility for that specific offer. Unverified coupons, generic
    cashback, payment-method discounts without eligibility, membership benefits, and
    conditional promotions are retained for display but never subtracted.
    """

    kind: AdjustmentKind
    amount: Decimal | None
    source: str = Field(min_length=1, max_length=500)
    eligibility: AdjustmentEligibility
    observed_at: datetime | None
    confidence: ConfidenceLevel

    @field_validator("source")
    @classmethod
    def _strip_source(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Adjustment source must not be blank.")
        return stripped

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: Decimal | None) -> Decimal | None:
        validated = validate_non_negative_amount(value, field_name="amount")
        return None if validated is None else quantize_money(validated)

    @field_validator("observed_at")
    @classmethod
    def _require_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Adjustment observed_at must be timezone-aware.")
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def affects_effective_price(self) -> bool:
        """True only when this adjustment is verified-eligible to change effective_price."""
        return (
            self.eligibility is AdjustmentEligibility.VERIFIED_ELIGIBLE
            and self.amount is not None
            and self.kind in (_PROMOTIONAL_KINDS | _FEE_KINDS)
        )


class SellerSnapshot(_FrozenModel):
    """Seller facts available for ranking. Missing seller is a first-class state."""

    seller_id: uuid.UUID | None = None
    name: str | None = None
    is_first_party: bool | None = None
    is_active: bool | None = None

    @property
    def quality_score(self) -> int:
        """Deterministic seller-quality rank; higher is better. 0 means unknown/missing."""
        if self.seller_id is None and not (self.name and self.name.strip()):
            return 0
        score = 1
        if self.is_active is True:
            score += 1
        if self.is_first_party is True:
            score += 2
        return score


class OfferInput(_FrozenModel):
    """One retailer/seller offer as the comparison engine sees it.

    Built from a `RetailerProduct` plus its latest `PriceSnapshot` (and optional persisted
    promotional adjustments). Missing observation, price, seller, or delivery is represented
    as `None` — never invented.
    """

    offer_id: str = Field(min_length=1, max_length=200)
    variant_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_slug: str
    retailer_name: str
    retailer_product_id: uuid.UUID
    source_url: str | None = None
    source_type: SourceType | None = None
    observed_at: datetime | None = None
    currency: str = "INR"
    displayed_price: Decimal | None = None
    mrp: Decimal | None = None
    source_effective_price: Decimal | None = None
    delivery_fee: Decimal | None = None
    platform_fee: Decimal | None = None
    availability: AvailabilityStatus = AvailabilityStatus.UNKNOWN
    observation_confidence: ConfidenceLevel | None = None
    seller: SellerSnapshot = Field(default_factory=SellerSnapshot)
    promotional_adjustments: tuple[PriceAdjustment, ...] = ()

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)

    @field_validator("observed_at")
    @classmethod
    def _require_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Offer observed_at must be timezone-aware.")
        return value

    @field_validator(
        "displayed_price", "mrp", "source_effective_price", "delivery_fee", "platform_fee"
    )
    @classmethod
    def _validate_optional_amount(cls, value: Decimal | None) -> Decimal | None:
        return optional_money(value, field_name="amount")


class DataFreshness(_FrozenModel):
    """Freshness summary derived only from actual observation timestamps."""

    status: FreshnessStatus
    as_of: datetime
    observed_at: datetime | None = None
    age_seconds: float | None = None
    oldest_observation: datetime | None = None
    newest_observation: datetime | None = None
    stale_offer_count: int = 0
    missing_observation_count: int = 0
    offer_count: int = 0


class ComparedOffer(_FrozenModel):
    """One ranked offer with verified, displayed, and unverified prices kept distinct."""

    offer_id: str
    variant_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_slug: str
    retailer_name: str
    retailer_product_id: uuid.UUID
    seller: SellerSnapshot
    displayed_price: Decimal | None
    mrp: Decimal | None
    discount_percentage: Decimal | None
    coupon_discount: Decimal | None
    payment_discount: Decimal | None
    cashback: Decimal | None
    delivery_fee: Decimal | None
    platform_fee: Decimal | None
    effective_price: Decimal | None
    unverified_estimated_price: Decimal | None
    unverified_price_kind: PriceKind | None = None
    source_effective_price: Decimal | None
    price_kind: PriceKind
    availability: AvailabilityStatus
    source_url: str | None
    source_type: SourceType | None
    observation_timestamp: datetime | None
    confidence: ConfidenceLevel
    observation_confidence: ConfidenceLevel | None
    freshness: DataFreshness
    adjustments: tuple[PriceAdjustment, ...]
    currency: str
    rank: int
    is_available: bool
    can_win_verified_ranking: bool


class RankingExplanation(_FrozenModel):
    """Explainable record of why one offer was selected."""

    criterion: RankingCriterion
    reason: str
    tie_breakers_applied: tuple[RankingCriterion, ...] = ()
    selected_offer_id: str | None = None


class VariantComparison(_FrozenModel):
    """Comparison result for a single product variant. Variants are never mixed."""

    variant_id: uuid.UUID
    variant_key: str | None = None
    offers: tuple[ComparedOffer, ...]
    lowest_verified_offer: ComparedOffer | None
    ranking: RankingExplanation
    data_freshness: DataFreshness


class ProductComparison(_FrozenModel):
    """Comparison result for every variant of a product."""

    product_id: uuid.UUID
    variants: tuple[VariantComparison, ...]
    data_freshness: DataFreshness
    as_of: datetime
