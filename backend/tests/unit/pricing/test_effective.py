"""Verified effective-price calculation and adjustment-safety rules."""

from decimal import Decimal

from app.domain.enums import AdjustmentEligibility, AdjustmentKind, ConfidenceLevel
from app.pricing.effective import (
    adjustment_applies_to_effective_price,
    amount_for_kind,
    collect_offer_adjustments,
    compute_effective_price,
    displayed_discount_percentage,
    lower_confidence,
)
from app.pricing.models import PriceAdjustment
from tests.unit.pricing.helpers import NOW, offer, promo


def test_displayed_discount_percentage_from_mrp() -> None:
    assert displayed_discount_percentage(Decimal("1000.00"), Decimal("800.00")) == Decimal("20.00")


def test_displayed_discount_percentage_missing_or_no_discount() -> None:
    assert displayed_discount_percentage(None, Decimal("800.00")) is None
    assert displayed_discount_percentage(Decimal("800.00"), Decimal("800.00")) is None
    assert displayed_discount_percentage(Decimal("0.00"), Decimal("0.00")) is None


def test_verified_coupon_reduces_effective_price() -> None:
    adjustments = collect_offer_adjustments(
        offer(displayed_price="1000.00", promotions=(promo(amount="100.00"),))
    )
    assert compute_effective_price(Decimal("1000.00"), adjustments) == Decimal("900.00")
    coupon = next(item for item in adjustments if item.kind is AdjustmentKind.COUPON)
    assert adjustment_applies_to_effective_price(coupon) is True


def test_ineligible_coupon_cannot_reduce_effective_price() -> None:
    coupon = promo(eligibility=AdjustmentEligibility.INELIGIBLE, amount="500.00")
    adjustments = collect_offer_adjustments(offer(displayed_price="1000.00", promotions=(coupon,)))
    assert compute_effective_price(Decimal("1000.00"), adjustments) == Decimal("1000.00")
    stored = next(item for item in adjustments if item.kind is AdjustmentKind.COUPON)
    assert stored.affects_effective_price is False
    assert stored.eligibility is AdjustmentEligibility.INELIGIBLE


def test_unverified_coupon_cannot_reduce_effective_price() -> None:
    coupon = promo(eligibility=AdjustmentEligibility.UNVERIFIED, amount="200.00")
    adjustments = collect_offer_adjustments(offer(displayed_price="1000.00", promotions=(coupon,)))
    verified = compute_effective_price(Decimal("1000.00"), adjustments)
    estimated = compute_effective_price(Decimal("1000.00"), adjustments, include_unverified=True)
    assert verified == Decimal("1000.00")
    assert estimated == Decimal("800.00")


def test_unverified_cashback_cannot_reduce_effective_price() -> None:
    cashback = promo(
        kind=AdjustmentKind.CASHBACK,
        eligibility=AdjustmentEligibility.UNVERIFIED,
        amount="50.00",
        source="test.generic_cashback",
    )
    adjustments = collect_offer_adjustments(offer(displayed_price="500.00", promotions=(cashback,)))
    assert compute_effective_price(Decimal("500.00"), adjustments) == Decimal("500.00")


def test_payment_specific_discount_without_eligibility_is_not_applied() -> None:
    payment = promo(
        kind=AdjustmentKind.PAYMENT_DISCOUNT,
        eligibility=AdjustmentEligibility.PAYMENT_METHOD_SPECIFIC,
        amount="80.00",
        source="test.bank_offer",
    )
    adjustments = collect_offer_adjustments(offer(displayed_price="900.00", promotions=(payment,)))
    assert compute_effective_price(Decimal("900.00"), adjustments) == Decimal("900.00")


def test_verified_payment_discount_is_applied() -> None:
    payment = promo(
        kind=AdjustmentKind.PAYMENT_DISCOUNT,
        eligibility=AdjustmentEligibility.VERIFIED_ELIGIBLE,
        amount="80.00",
        source="test.verified_bank_offer",
    )
    adjustments = collect_offer_adjustments(offer(displayed_price="900.00", promotions=(payment,)))
    assert compute_effective_price(Decimal("900.00"), adjustments) == Decimal("820.00")


def test_membership_only_and_conditional_promotions_are_not_applied() -> None:
    membership = promo(
        eligibility=AdjustmentEligibility.MEMBERSHIP_ONLY, amount="120.00", source="test.plus"
    )
    conditional = promo(
        kind=AdjustmentKind.CASHBACK,
        eligibility=AdjustmentEligibility.CONDITIONAL,
        amount="30.00",
        source="test.if_app_only",
    )
    adjustments = collect_offer_adjustments(
        offer(displayed_price="1000.00", promotions=(membership, conditional))
    )
    assert compute_effective_price(Decimal("1000.00"), adjustments) == Decimal("1000.00")


def test_missing_delivery_is_not_assumed_zero() -> None:
    adjustments = collect_offer_adjustments(offer(displayed_price="400.00", delivery_fee=None))
    delivery = next(item for item in adjustments if item.kind is AdjustmentKind.DELIVERY_FEE)
    assert delivery.eligibility is AdjustmentEligibility.UNAVAILABLE
    assert delivery.affects_effective_price is False
    assert compute_effective_price(Decimal("400.00"), adjustments) == Decimal("400.00")


def test_known_delivery_and_platform_fees_are_added() -> None:
    adjustments = collect_offer_adjustments(
        offer(displayed_price="400.00", delivery_fee="40.00", platform_fee="10.00")
    )
    assert compute_effective_price(Decimal("400.00"), adjustments) == Decimal("450.00")


def test_mrp_displayed_discount_is_not_applied_twice() -> None:
    adjustments = collect_offer_adjustments(offer(displayed_price="800.00", mrp="1000.00"))
    displayed = next(item for item in adjustments if item.kind is AdjustmentKind.DISPLAYED_DISCOUNT)
    assert displayed.amount == Decimal("200.00")
    assert displayed.affects_effective_price is False
    assert compute_effective_price(Decimal("800.00"), adjustments) == Decimal("800.00")


def test_coupon_on_one_offer_does_not_apply_universally() -> None:
    with_coupon = collect_offer_adjustments(
        offer(offer_id="a", displayed_price="1000.00", promotions=(promo(amount="100.00"),))
    )
    without = collect_offer_adjustments(offer(offer_id="b", displayed_price="1000.00"))
    assert compute_effective_price(Decimal("1000.00"), with_coupon) == Decimal("900.00")
    assert compute_effective_price(Decimal("1000.00"), without) == Decimal("1000.00")
    assert amount_for_kind(without, AdjustmentKind.COUPON) is None


def test_unavailable_adjustment_with_missing_amount_is_preserved() -> None:
    missing = PriceAdjustment(
        kind=AdjustmentKind.COUPON,
        amount=None,
        source="test.missing_coupon",
        eligibility=AdjustmentEligibility.UNAVAILABLE,
        observed_at=NOW,
        confidence=ConfidenceLevel.LOW,
    )
    adjustments = collect_offer_adjustments(offer(displayed_price="250.00", promotions=(missing,)))
    assert compute_effective_price(Decimal("250.00"), adjustments) == Decimal("250.00")
    stored = next(item for item in adjustments if item.kind is AdjustmentKind.COUPON)
    assert stored.amount is None
    assert stored.eligibility is AdjustmentEligibility.UNAVAILABLE


def test_effective_price_floors_at_zero() -> None:
    adjustments = collect_offer_adjustments(
        offer(displayed_price="50.00", promotions=(promo(amount="80.00"),))
    )
    assert compute_effective_price(Decimal("50.00"), adjustments) == Decimal("0.00")


def test_missing_displayed_price_yields_no_effective_price() -> None:
    adjustments = collect_offer_adjustments(offer(displayed_price=None))
    assert compute_effective_price(None, adjustments) is None


def test_lower_confidence_never_goes_below_low() -> None:
    assert lower_confidence(ConfidenceLevel.HIGH, 1) is ConfidenceLevel.MEDIUM
    assert lower_confidence(ConfidenceLevel.LOW, 5) is ConfidenceLevel.LOW
