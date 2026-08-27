"""Builders for price-comparison unit tests. All data is fictional fixture data."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.enums import (
    AdjustmentEligibility,
    AdjustmentKind,
    AvailabilityStatus,
    ConfidenceLevel,
    SourceType,
)
from app.pricing.config import PricingConfig
from app.pricing.engine import PriceComparisonEngine
from app.pricing.models import OfferInput, PriceAdjustment, SellerSnapshot

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)

VARIANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
VARIANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
RETAILER_A = UUID("11111111-1111-1111-1111-111111111111")
RETAILER_B = UUID("22222222-2222-2222-2222-222222222222")
RETAILER_C = UUID("33333333-3333-3333-3333-333333333333")


def promo(
    *,
    kind: AdjustmentKind = AdjustmentKind.COUPON,
    amount: Decimal | str | None = "100.00",
    eligibility: AdjustmentEligibility = AdjustmentEligibility.VERIFIED_ELIGIBLE,
    source: str = "test.fixture",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    observed_at: datetime | None = NOW,
) -> PriceAdjustment:
    return PriceAdjustment(
        kind=kind,
        amount=None if amount is None else Decimal(amount),
        source=source,
        eligibility=eligibility,
        observed_at=observed_at,
        confidence=confidence,
    )


def seller(
    *,
    present: bool = True,
    name: str = "Fictional Seller",
    first_party: bool = False,
    active: bool = True,
) -> SellerSnapshot:
    if not present:
        return SellerSnapshot()
    return SellerSnapshot(
        seller_id=uuid4(),
        name=name,
        is_first_party=first_party,
        is_active=active,
    )


def offer(
    *,
    offer_id: str = "offer-a",
    variant_id: UUID = VARIANT_A,
    retailer_id: UUID = RETAILER_A,
    retailer_slug: str = "fictional-mart-a",
    retailer_name: str = "Fictional Mart A",
    displayed_price: Decimal | str | None = "999.00",
    mrp: Decimal | str | None = None,
    delivery_fee: Decimal | str | None = None,
    platform_fee: Decimal | str | None = None,
    source_effective_price: Decimal | str | None = None,
    availability: AvailabilityStatus = AvailabilityStatus.IN_STOCK,
    observed_at: datetime | None = NOW,
    observation_confidence: ConfidenceLevel | None = ConfidenceLevel.HIGH,
    source_url: str | None = "https://fictional-mart-a.example.test/p/1",
    source_type: SourceType | None = SourceType.PRODUCT_FEED,
    seller_info: SellerSnapshot | None = None,
    promotions: tuple[PriceAdjustment, ...] = (),
    listing_id: UUID | None = None,
) -> OfferInput:
    def _dec(value: Decimal | str | None) -> Decimal | None:
        if value is None:
            return None
        return value if isinstance(value, Decimal) else Decimal(value)

    return OfferInput(
        offer_id=offer_id,
        variant_id=variant_id,
        retailer_id=retailer_id,
        retailer_slug=retailer_slug,
        retailer_name=retailer_name,
        retailer_product_id=listing_id or uuid4(),
        source_url=source_url,
        source_type=source_type,
        observed_at=observed_at,
        displayed_price=_dec(displayed_price),
        mrp=_dec(mrp),
        source_effective_price=_dec(source_effective_price),
        delivery_fee=_dec(delivery_fee),
        platform_fee=_dec(platform_fee),
        availability=availability,
        observation_confidence=observation_confidence,
        seller=seller_info if seller_info is not None else seller(),
        promotional_adjustments=promotions,
    )


def engine(config: PricingConfig | None = None) -> PriceComparisonEngine:
    return PriceComparisonEngine(config=config or PricingConfig(_env_file=None), clock=lambda: NOW)
