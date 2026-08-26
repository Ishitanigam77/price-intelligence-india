"""API schemas for `GET /api/v1/products/{product_id}/prices`.

These DTOs expose the price comparison engine's result. Observed, calculated, and unverified
estimated values are kept as separate fields; an unverified promotional figure is never the
`effective_price` used for ranking.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AdjustmentEligibility,
    AdjustmentKind,
    AvailabilityStatus,
    ConfidenceLevel,
    SourceType,
)
from app.pricing.enums import FreshnessStatus, PriceKind, RankingCriterion
from app.pricing.models import (
    ComparedOffer,
    DataFreshness,
    PriceAdjustment,
    ProductComparison,
    RankingExplanation,
    SellerSnapshot,
    VariantComparison,
)


class PriceAdjustmentRead(BaseModel):
    """One itemized adjustment with source, eligibility, timestamp, and confidence."""

    model_config = ConfigDict(from_attributes=True)

    kind: AdjustmentKind
    amount: Decimal | None = None
    source: str
    eligibility: AdjustmentEligibility
    observed_at: datetime | None = None
    confidence: ConfidenceLevel
    affects_effective_price: bool


class OfferSellerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seller_id: uuid.UUID | None = None
    name: str | None = None
    is_first_party: bool | None = None
    is_active: bool | None = None
    quality_score: int


class DataFreshnessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: FreshnessStatus
    as_of: datetime
    observed_at: datetime | None = None
    age_seconds: float | None = None
    oldest_observation: datetime | None = None
    newest_observation: datetime | None = None
    stale_offer_count: int = 0
    missing_observation_count: int = 0
    offer_count: int = 0


class RankingReasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    criterion: RankingCriterion
    reason: str
    tie_breakers_applied: list[RankingCriterion] = Field(default_factory=list)
    selected_offer_id: str | None = None


class ComparedOfferRead(BaseModel):
    """One retailer/seller offer as returned by the comparison API."""

    model_config = ConfigDict(from_attributes=True)

    offer_id: str
    variant_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_slug: str
    retailer_name: str
    retailer_product_id: uuid.UUID
    seller: OfferSellerRead
    displayed_price: Decimal | None = None
    mrp: Decimal | None = None
    discount_percentage: Decimal | None = None
    coupon_discount: Decimal | None = None
    payment_discount: Decimal | None = None
    cashback: Decimal | None = None
    delivery_fee: Decimal | None = None
    platform_fee: Decimal | None = None
    effective_price: Decimal | None = None
    unverified_estimated_price: Decimal | None = None
    unverified_price_kind: PriceKind | None = None
    source_effective_price: Decimal | None = None
    price_kind: PriceKind
    availability: AvailabilityStatus
    source_url: str | None = None
    source_type: SourceType | None = None
    observation_timestamp: datetime | None = None
    confidence: ConfidenceLevel
    observation_confidence: ConfidenceLevel | None = None
    freshness: DataFreshnessRead
    adjustments: list[PriceAdjustmentRead]
    currency: str
    rank: int
    is_available: bool
    can_win_verified_ranking: bool


class VariantPricesRead(BaseModel):
    variant_id: uuid.UUID
    variant_key: str | None = None
    offers: list[ComparedOfferRead]
    lowest_verified_offer: ComparedOfferRead | None = None
    ranking_reason: RankingReasonRead
    data_freshness: DataFreshnessRead


class ProductPricesRead(BaseModel):
    """Response for `GET /api/v1/products/{product_id}/prices`."""

    product_id: uuid.UUID
    variants: list[VariantPricesRead]
    lowest_verified_offer: ComparedOfferRead | None = None
    ranking_reason: RankingReasonRead | None = None
    data_freshness: DataFreshnessRead
    as_of: datetime


def _seller_read(seller: SellerSnapshot) -> OfferSellerRead:
    return OfferSellerRead(
        seller_id=seller.seller_id,
        name=seller.name,
        is_first_party=seller.is_first_party,
        is_active=seller.is_active,
        quality_score=seller.quality_score,
    )


def _adjustment_read(adjustment: PriceAdjustment) -> PriceAdjustmentRead:
    return PriceAdjustmentRead(
        kind=adjustment.kind,
        amount=adjustment.amount,
        source=adjustment.source,
        eligibility=adjustment.eligibility,
        observed_at=adjustment.observed_at,
        confidence=adjustment.confidence,
        affects_effective_price=adjustment.affects_effective_price,
    )


def _freshness_read(freshness: DataFreshness) -> DataFreshnessRead:
    return DataFreshnessRead.model_validate(freshness)


def _ranking_read(ranking: RankingExplanation) -> RankingReasonRead:
    return RankingReasonRead(
        criterion=ranking.criterion,
        reason=ranking.reason,
        tie_breakers_applied=list(ranking.tie_breakers_applied),
        selected_offer_id=ranking.selected_offer_id,
    )


def offer_read(offer: ComparedOffer) -> ComparedOfferRead:
    return ComparedOfferRead(
        offer_id=offer.offer_id,
        variant_id=offer.variant_id,
        retailer_id=offer.retailer_id,
        retailer_slug=offer.retailer_slug,
        retailer_name=offer.retailer_name,
        retailer_product_id=offer.retailer_product_id,
        seller=_seller_read(offer.seller),
        displayed_price=offer.displayed_price,
        mrp=offer.mrp,
        discount_percentage=offer.discount_percentage,
        coupon_discount=offer.coupon_discount,
        payment_discount=offer.payment_discount,
        cashback=offer.cashback,
        delivery_fee=offer.delivery_fee,
        platform_fee=offer.platform_fee,
        effective_price=offer.effective_price,
        unverified_estimated_price=offer.unverified_estimated_price,
        unverified_price_kind=offer.unverified_price_kind,
        source_effective_price=offer.source_effective_price,
        price_kind=offer.price_kind,
        availability=offer.availability,
        source_url=offer.source_url,
        source_type=offer.source_type,
        observation_timestamp=offer.observation_timestamp,
        confidence=offer.confidence,
        observation_confidence=offer.observation_confidence,
        freshness=_freshness_read(offer.freshness),
        adjustments=[_adjustment_read(item) for item in offer.adjustments],
        currency=offer.currency,
        rank=offer.rank,
        is_available=offer.is_available,
        can_win_verified_ranking=offer.can_win_verified_ranking,
    )


def variant_prices_read(variant: VariantComparison) -> VariantPricesRead:
    return VariantPricesRead(
        variant_id=variant.variant_id,
        variant_key=variant.variant_key,
        offers=[offer_read(item) for item in variant.offers],
        lowest_verified_offer=(
            offer_read(variant.lowest_verified_offer)
            if variant.lowest_verified_offer is not None
            else None
        ),
        ranking_reason=_ranking_read(variant.ranking),
        data_freshness=_freshness_read(variant.data_freshness),
    )


def product_prices_read(comparison: ProductComparison) -> ProductPricesRead:
    """Map a domain comparison onto the API schema.

    `lowest_verified_offer` at product level is omitted whenever the product has more than one
    variant, so different variants are never combined into a single "best price". A single-
    variant product copies that variant's winner for convenience.
    """
    variant_reads = [variant_prices_read(item) for item in comparison.variants]
    lowest = None
    ranking = None
    if len(variant_reads) == 1:
        lowest = variant_reads[0].lowest_verified_offer
        ranking = variant_reads[0].ranking_reason
    return ProductPricesRead(
        product_id=comparison.product_id,
        variants=variant_reads,
        lowest_verified_offer=lowest,
        ranking_reason=ranking,
        data_freshness=_freshness_read(comparison.data_freshness),
        as_of=comparison.as_of,
    )
