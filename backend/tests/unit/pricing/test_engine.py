"""End-to-end price comparison engine: offers, ranking, freshness, provenance."""

from datetime import timedelta
from decimal import Decimal

from app.domain.enums import (
    AdjustmentEligibility,
    AdjustmentKind,
    AvailabilityStatus,
    ConfidenceLevel,
)
from app.pricing.enums import FreshnessStatus, PriceKind, RankingCriterion
from tests.unit.pricing.helpers import (
    NOW,
    RETAILER_A,
    RETAILER_B,
    RETAILER_C,
    VARIANT_A,
    VARIANT_B,
    engine,
    offer,
    promo,
    seller,
)


def test_multiple_retailers_and_sellers_remain_separate() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="a-s1",
                retailer_id=RETAILER_A,
                retailer_slug="fictional-mart-a",
                displayed_price="999.00",
                seller_info=seller(name="Seller One"),
            ),
            offer(
                offer_id="a-s2",
                retailer_id=RETAILER_A,
                retailer_slug="fictional-mart-a",
                displayed_price="989.00",
                seller_info=seller(name="Seller Two"),
            ),
            offer(
                offer_id="b-s1",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
                displayed_price="1010.00",
                seller_info=seller(name="Seller Three"),
            ),
        ],
    )
    assert {item.offer_id for item in result.offers} == {"a-s1", "a-s2", "b-s1"}
    assert {item.retailer_slug for item in result.offers} == {
        "fictional-mart-a",
        "fictional-mart-b",
    }
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "a-s2"
    sellers = {item.seller.name for item in result.offers}
    assert sellers == {"Seller One", "Seller Two", "Seller Three"}


def test_same_product_different_prices_picks_lowest_verified() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(offer_id="high", displayed_price="1500.00", retailer_slug="fictional-mart-a"),
            offer(
                offer_id="low",
                displayed_price="1100.00",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
            ),
        ],
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "low"
    assert result.ranking.criterion is RankingCriterion.VERIFIED_EFFECTIVE_PRICE


def test_mrp_and_displayed_discount_are_exposed() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [offer(offer_id="disc", displayed_price="800.00", mrp="1000.00")],
    )
    offer_out = result.offers[0]
    assert offer_out.discount_percentage == Decimal("20.00")
    assert offer_out.mrp == Decimal("1000.00")
    assert offer_out.effective_price == Decimal("800.00")
    displayed = next(
        item for item in offer_out.adjustments if item.kind is AdjustmentKind.DISPLAYED_DISCOUNT
    )
    assert displayed.amount == Decimal("200.00")
    assert displayed.affects_effective_price is False
    assert displayed.source == "price_snapshot.mrp_vs_displayed"


def test_verified_coupon_wins_on_effective_price() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="plain",
                displayed_price="900.00",
                retailer_slug="fictional-mart-a",
            ),
            offer(
                offer_id="coupon",
                displayed_price="950.00",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
                promotions=(promo(amount="100.00", source="test.verified_coupon"),),
            ),
        ],
    )
    winner = result.lowest_verified_offer
    assert winner is not None
    assert winner.offer_id == "coupon"
    assert winner.effective_price == Decimal("850.00")
    assert winner.coupon_discount == Decimal("100.00")
    assert winner.price_kind is PriceKind.VERIFIED_EFFECTIVE
    coupon = next(item for item in winner.adjustments if item.kind is AdjustmentKind.COUPON)
    assert coupon.source == "test.verified_coupon"
    assert coupon.eligibility is AdjustmentEligibility.VERIFIED_ELIGIBLE
    assert coupon.observed_at == NOW
    assert coupon.confidence is ConfidenceLevel.HIGH
    assert coupon.affects_effective_price is True


def test_unverified_coupon_is_labeled_estimate_and_does_not_win() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="plain",
                displayed_price="900.00",
                retailer_slug="fictional-mart-a",
            ),
            offer(
                offer_id="unverified-coupon",
                displayed_price="950.00",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
                promotions=(
                    promo(
                        amount="200.00",
                        eligibility=AdjustmentEligibility.UNVERIFIED,
                        source="test.unverified_coupon",
                    ),
                ),
            ),
        ],
    )
    winner = result.lowest_verified_offer
    assert winner is not None
    assert winner.offer_id == "plain"
    unverified = next(item for item in result.offers if item.offer_id == "unverified-coupon")
    assert unverified.effective_price == Decimal("950.00")
    assert unverified.unverified_estimated_price == Decimal("750.00")
    assert unverified.unverified_price_kind is PriceKind.ESTIMATED_UNVERIFIED
    assert unverified.price_kind is not PriceKind.ESTIMATED_UNVERIFIED
    assert result.ranking.reason
    assert "Unverified" in result.ranking.reason or "verified" in result.ranking.reason.lower()


def test_coupon_eligibility_is_per_offer() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="eligible",
                displayed_price="1000.00",
                promotions=(
                    promo(amount="150.00", eligibility=AdjustmentEligibility.VERIFIED_ELIGIBLE),
                ),
                retailer_slug="fictional-mart-a",
            ),
            offer(
                offer_id="ineligible",
                displayed_price="1000.00",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
                promotions=(promo(amount="150.00", eligibility=AdjustmentEligibility.INELIGIBLE),),
            ),
        ],
    )
    winner = result.lowest_verified_offer
    assert winner is not None
    assert winner.offer_id == "eligible"
    assert winner.effective_price == Decimal("850.00")
    other = next(item for item in result.offers if item.offer_id == "ineligible")
    assert other.effective_price == Decimal("1000.00")
    assert other.coupon_discount == Decimal("150.00")


def test_cashback_and_platform_fee_and_delivery_charges() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="fees",
                displayed_price="1000.00",
                delivery_fee="50.00",
                platform_fee="20.00",
                promotions=(
                    promo(
                        kind=AdjustmentKind.CASHBACK,
                        amount="100.00",
                        eligibility=AdjustmentEligibility.VERIFIED_ELIGIBLE,
                        source="test.verified_cashback",
                    ),
                ),
            )
        ],
    )
    offer_out = result.offers[0]
    assert offer_out.delivery_fee == Decimal("50.00")
    assert offer_out.platform_fee == Decimal("20.00")
    assert offer_out.cashback == Decimal("100.00")
    assert offer_out.effective_price == Decimal("970.00")
    assert offer_out.price_kind is PriceKind.VERIFIED_EFFECTIVE


def test_missing_price_seller_and_delivery_information() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="incomplete",
                displayed_price=None,
                observed_at=None,
                observation_confidence=None,
                source_type=None,
                delivery_fee=None,
                seller_info=seller(present=False),
            ),
            offer(
                offer_id="complete",
                displayed_price="700.00",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
            ),
        ],
    )
    incomplete = next(item for item in result.offers if item.offer_id == "incomplete")
    assert incomplete.displayed_price is None
    assert incomplete.effective_price is None
    assert incomplete.observation_timestamp is None
    assert incomplete.freshness.status is FreshnessStatus.MISSING
    assert incomplete.seller.quality_score == 0
    assert incomplete.can_win_verified_ranking is False
    assert incomplete.confidence is ConfidenceLevel.LOW
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "complete"


def test_stale_observation_lowers_confidence_and_is_labeled() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="stale",
                displayed_price="500.00",
                observed_at=NOW - timedelta(hours=72),
                observation_confidence=ConfidenceLevel.HIGH,
            )
        ],
    )
    offer_out = result.offers[0]
    assert offer_out.freshness.status is FreshnessStatus.STALE
    assert offer_out.freshness.observed_at == NOW - timedelta(hours=72)
    assert offer_out.confidence is ConfidenceLevel.MEDIUM
    assert offer_out.observation_confidence is ConfidenceLevel.HIGH


def test_source_provenance_is_preserved() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="src",
                source_url="https://fictional-mart-a.example.test/listing/42",
                displayed_price="333.00",
            )
        ],
    )
    offer_out = result.offers[0]
    assert offer_out.source_url == "https://fictional-mart-a.example.test/listing/42"
    assert offer_out.source_type is not None
    assert offer_out.observation_timestamp == NOW
    assert offer_out.retailer_slug == "fictional-mart-a"


def test_source_effective_price_is_exposed_but_not_used_as_unverified_promo() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="src-eff",
                displayed_price="1000.00",
                source_effective_price="700.00",
                promotions=(promo(amount="300.00", eligibility=AdjustmentEligibility.UNVERIFIED),),
            )
        ],
    )
    offer_out = result.offers[0]
    assert offer_out.source_effective_price == Decimal("700.00")
    assert offer_out.effective_price == Decimal("1000.00")
    assert offer_out.unverified_estimated_price == Decimal("700.00")
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.effective_price == Decimal("1000.00")


def test_displayed_price_fallback_when_no_verified_promotions() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(offer_id="a", displayed_price="880.00", retailer_slug="fictional-mart-a"),
            offer(
                offer_id="b",
                displayed_price="870.00",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
            ),
        ],
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "b"
    assert result.lowest_verified_offer.price_kind is PriceKind.DISPLAYED_ONLY
    assert result.ranking.reason


def test_variants_are_never_combined() -> None:
    comparison = engine().compare_product(
        VARIANT_A,
        {
            VARIANT_A: [
                offer(
                    offer_id="a-expensive",
                    variant_id=VARIANT_A,
                    displayed_price="2000.00",
                    retailer_slug="fictional-mart-a",
                )
            ],
            VARIANT_B: [
                offer(
                    offer_id="b-cheap",
                    variant_id=VARIANT_B,
                    displayed_price="500.00",
                    retailer_id=RETAILER_B,
                    retailer_slug="fictional-mart-b",
                )
            ],
        },
        variant_keys={VARIANT_A: "storage=128gb", VARIANT_B: "storage=256gb"},
    )
    by_id = {item.variant_id: item for item in comparison.variants}
    assert by_id[VARIANT_A].lowest_verified_offer is not None
    assert by_id[VARIANT_A].lowest_verified_offer.offer_id == "a-expensive"
    assert by_id[VARIANT_B].lowest_verified_offer is not None
    assert by_id[VARIANT_B].lowest_verified_offer.offer_id == "b-cheap"
    assert all(item.variant_id == VARIANT_A for item in by_id[VARIANT_A].offers)
    assert all(item.variant_id == VARIANT_B for item in by_id[VARIANT_B].offers)


def test_data_freshness_aggregates_across_offers() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(offer_id="fresh", displayed_price="800.00", observed_at=NOW),
            offer(
                offer_id="stale",
                displayed_price="790.00",
                observed_at=NOW - timedelta(days=3),
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
            ),
            offer(
                offer_id="missing",
                displayed_price=None,
                observed_at=None,
                retailer_id=RETAILER_C,
                retailer_slug="fictional-mart-c",
            ),
        ],
    )
    assert result.data_freshness.status is FreshnessStatus.STALE
    assert result.data_freshness.stale_offer_count == 1
    assert result.data_freshness.missing_observation_count == 1
    assert result.data_freshness.newest_observation == NOW


def test_all_unavailable_yields_no_verified_winner() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="oos",
                displayed_price="100.00",
                availability=AvailabilityStatus.OUT_OF_STOCK,
            )
        ],
    )
    assert result.lowest_verified_offer is None
    assert result.ranking.criterion is RankingCriterion.NO_APPLICABLE_OFFER
    assert (
        "unavailable" in result.ranking.reason.lower()
        or "out of stock" in result.ranking.reason.lower()
    )


def test_ranks_are_one_based_and_stable() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="c",
                displayed_price="300.00",
                retailer_slug="fictional-mart-c",
                retailer_id=RETAILER_C,
            ),
            offer(offer_id="a", displayed_price="100.00", retailer_slug="fictional-mart-a"),
            offer(
                offer_id="b",
                displayed_price="200.00",
                retailer_slug="fictional-mart-b",
                retailer_id=RETAILER_B,
            ),
        ],
    )
    assert [item.offer_id for item in result.offers] == ["a", "b", "c"]
    assert [item.rank for item in result.offers] == [1, 2, 3]
