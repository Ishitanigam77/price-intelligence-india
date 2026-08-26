"""Verified effective-price calculation with adjustment-safety rules.

Never assumes a coupon, cashback, payment discount, or other promotion applies universally.
Missing inputs are left unset; they are never guessed.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.enums import (
    AdjustmentEligibility,
    AdjustmentKind,
    AvailabilityStatus,
    ConfidenceLevel,
)
from app.pricing.enums import FreshnessStatus, PriceKind
from app.pricing.models import OfferInput, PriceAdjustment
from app.pricing.money import quantize_money

_PROMOTIONAL_KINDS = frozenset(
    {
        AdjustmentKind.COUPON,
        AdjustmentKind.PAYMENT_DISCOUNT,
        AdjustmentKind.CASHBACK,
    }
)
_FEE_KINDS = frozenset({AdjustmentKind.DELIVERY_FEE, AdjustmentKind.PLATFORM_FEE})
_CONFIDENCE_ORDER = (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)


def displayed_discount_percentage(mrp: Decimal | None, displayed: Decimal | None) -> Decimal | None:
    """Return the displayed discount vs MRP, or `None` when it cannot be computed."""
    if mrp is None or displayed is None or mrp <= 0 or displayed >= mrp:
        return None
    percent = (mrp - displayed) / mrp * Decimal("100")
    return quantize_money(percent)


def adjustment_applies_to_effective_price(adjustment: PriceAdjustment) -> bool:
    """Whether this adjustment is allowed to change the verified effective price."""
    return adjustment.affects_effective_price


def synthesize_fee_adjustment(
    *,
    kind: AdjustmentKind,
    amount: Decimal | None,
    observed_at,
    confidence: ConfidenceLevel,
    source: str,
) -> PriceAdjustment:
    """Build a fee adjustment from an observed snapshot column.

    A missing fee is `unavailable` and must not be treated as free delivery/no platform fee.
    """
    if amount is None:
        eligibility = AdjustmentEligibility.UNAVAILABLE
        confidence_out = lower_confidence(confidence)
    else:
        eligibility = AdjustmentEligibility.VERIFIED_ELIGIBLE
        confidence_out = confidence
    return PriceAdjustment(
        kind=kind,
        amount=amount,
        source=source,
        eligibility=eligibility,
        observed_at=observed_at,
        confidence=confidence_out,
    )


def synthesize_displayed_discount(
    *,
    mrp: Decimal | None,
    displayed: Decimal | None,
    observed_at,
    confidence: ConfidenceLevel,
) -> PriceAdjustment:
    """Informational MRP-vs-displayed discount. Never applied on top of displayed_price."""
    if mrp is None or displayed is None:
        return PriceAdjustment(
            kind=AdjustmentKind.DISPLAYED_DISCOUNT,
            amount=None,
            source="price_snapshot.mrp_vs_displayed",
            eligibility=AdjustmentEligibility.UNAVAILABLE,
            observed_at=observed_at,
            confidence=lower_confidence(confidence),
        )
    if displayed >= mrp:
        return PriceAdjustment(
            kind=AdjustmentKind.DISPLAYED_DISCOUNT,
            amount=Decimal("0.00"),
            source="price_snapshot.mrp_vs_displayed",
            eligibility=AdjustmentEligibility.VERIFIED_ELIGIBLE,
            observed_at=observed_at,
            confidence=confidence,
        )
    return PriceAdjustment(
        kind=AdjustmentKind.DISPLAYED_DISCOUNT,
        amount=quantize_money(mrp - displayed),
        source="price_snapshot.mrp_vs_displayed",
        eligibility=AdjustmentEligibility.VERIFIED_ELIGIBLE,
        observed_at=observed_at,
        confidence=confidence,
    )


def collect_offer_adjustments(offer: OfferInput) -> tuple[PriceAdjustment, ...]:
    """Combine snapshot-derived fees/MRP discount with caller-supplied promotional adjustments.

    Promotional adjustments are taken as provided — this function never upgrades eligibility.
    """
    confidence = offer.observation_confidence or ConfidenceLevel.LOW
    derived = [
        synthesize_displayed_discount(
            mrp=offer.mrp,
            displayed=offer.displayed_price,
            observed_at=offer.observed_at,
            confidence=confidence,
        ),
        synthesize_fee_adjustment(
            kind=AdjustmentKind.DELIVERY_FEE,
            amount=offer.delivery_fee,
            observed_at=offer.observed_at,
            confidence=confidence,
            source="price_snapshot.delivery_fee",
        ),
        synthesize_fee_adjustment(
            kind=AdjustmentKind.PLATFORM_FEE,
            amount=offer.platform_fee,
            observed_at=offer.observed_at,
            confidence=confidence,
            source="price_snapshot.platform_fee",
        ),
    ]
    return tuple(derived) + offer.promotional_adjustments


def amount_for_kind(
    adjustments: tuple[PriceAdjustment, ...], kind: AdjustmentKind
) -> Decimal | None:
    """Sum observed amounts of `kind`, regardless of eligibility. `None` if none recorded."""
    matching = [
        item.amount for item in adjustments if item.kind is kind and item.amount is not None
    ]
    if not matching:
        return None
    return quantize_money(sum(matching, Decimal("0.00")))


def lower_confidence(current: ConfidenceLevel, steps: int = 1) -> ConfidenceLevel:
    """Drop confidence by `steps` levels, never below LOW."""
    idx = _CONFIDENCE_ORDER.index(current)
    return _CONFIDENCE_ORDER[min(idx + max(steps, 0), len(_CONFIDENCE_ORDER) - 1)]


def resolve_offer_confidence(
    offer: OfferInput,
    adjustments: tuple[PriceAdjustment, ...],
    freshness_status: FreshnessStatus,
) -> ConfidenceLevel:
    """Start from the observation's confidence and lower it when data is weak or unverified."""
    current = offer.observation_confidence or ConfidenceLevel.LOW
    steps = 0
    if freshness_status is FreshnessStatus.STALE:
        steps += 1
    elif freshness_status is FreshnessStatus.MISSING:
        steps += 2
    if offer.displayed_price is None:
        steps += 1
    if offer.seller.quality_score == 0:
        steps += 1
    if offer.delivery_fee is None:
        steps += 1
    unsafe = [
        item
        for item in adjustments
        if item.kind in _PROMOTIONAL_KINDS
        and item.eligibility is not AdjustmentEligibility.VERIFIED_ELIGIBLE
        and item.eligibility is not AdjustmentEligibility.UNAVAILABLE
    ]
    if unsafe:
        steps += 1
    return lower_confidence(current, steps)


def compute_effective_price(
    displayed_price: Decimal | None,
    adjustments: tuple[PriceAdjustment, ...],
    *,
    include_unverified: bool = False,
) -> Decimal | None:
    """Compute a payable price from displayed_price plus/minus adjustments.

    When `include_unverified` is false (the default used for ranking), only verified-eligible
    fees and promotions are applied. Unverified/ineligible/conditional/membership/payment-
    specific promotions are ignored. Missing fees are not assumed to be zero.
    """
    if displayed_price is None:
        return None
    total = displayed_price
    for adjustment in adjustments:
        if adjustment.amount is None:
            continue
        if adjustment.kind in _FEE_KINDS:
            if include_unverified or adjustment.affects_effective_price:
                total += adjustment.amount
            continue
        if adjustment.kind not in _PROMOTIONAL_KINDS:
            continue
        if include_unverified:
            if adjustment.eligibility is not AdjustmentEligibility.INELIGIBLE:
                total -= adjustment.amount
            continue
        if adjustment.affects_effective_price:
            total -= adjustment.amount
    if total < 0:
        total = Decimal("0.00")
    return quantize_money(total)


def classify_price_kind(
    *,
    displayed_price: Decimal | None,
    verified_effective: Decimal | None,
    adjustments: tuple[PriceAdjustment, ...],
) -> PriceKind:
    """Classify the *ranking* price: verified effective vs displayed-only.

    An unverified estimate, when computed, is stored separately and never used as this kind.
    """
    if displayed_price is None or verified_effective is None:
        return PriceKind.DISPLAYED_ONLY
    applied_verified = any(
        item.affects_effective_price and item.kind in (_PROMOTIONAL_KINDS | _FEE_KINDS)
        for item in adjustments
    )
    if applied_verified:
        return PriceKind.VERIFIED_EFFECTIVE
    return PriceKind.DISPLAYED_ONLY


def is_offer_available(availability: AvailabilityStatus) -> bool:
    return availability in {AvailabilityStatus.IN_STOCK, AvailabilityStatus.LIMITED_STOCK}


def can_win_verified_ranking(
    *,
    is_available: bool,
    displayed_price: Decimal | None,
    verified_effective: Decimal | None,
) -> bool:
    """Unavailable offers and offers with no known price cannot win verified ranking."""
    return is_available and displayed_price is not None and verified_effective is not None
