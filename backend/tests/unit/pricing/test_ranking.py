"""Deterministic ranking and ranking-reason explanations."""

from decimal import Decimal
from uuid import uuid4

from app.domain.enums import AvailabilityStatus
from app.pricing.enums import RankingCriterion
from tests.unit.pricing.helpers import (
    RETAILER_A,
    RETAILER_B,
    VARIANT_A,
    engine,
    offer,
    seller,
)


def _compare(*offers):
    return engine().compare_variant(VARIANT_A, offers)


def test_lowest_verified_effective_price_wins() -> None:
    result = _compare(
        offer(
            offer_id="expensive",
            retailer_id=RETAILER_A,
            retailer_slug="fictional-mart-a",
            displayed_price="1200.00",
        ),
        offer(
            offer_id="cheap",
            retailer_id=RETAILER_B,
            retailer_slug="fictional-mart-b",
            displayed_price="900.00",
        ),
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "cheap"
    assert result.lowest_verified_offer.effective_price == Decimal("900.00")
    assert result.ranking.criterion is RankingCriterion.VERIFIED_EFFECTIVE_PRICE
    assert "900.00" in result.ranking.reason


def test_unavailable_offer_cannot_win_verified_ranking() -> None:
    result = _compare(
        offer(
            offer_id="oos-cheap",
            displayed_price="100.00",
            availability=AvailabilityStatus.OUT_OF_STOCK,
            retailer_slug="fictional-mart-a",
        ),
        offer(
            offer_id="in-stock",
            displayed_price="500.00",
            availability=AvailabilityStatus.IN_STOCK,
            retailer_slug="fictional-mart-b",
            retailer_id=RETAILER_B,
        ),
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "in-stock"
    oos = next(item for item in result.offers if item.offer_id == "oos-cheap")
    assert oos.can_win_verified_ranking is False
    assert oos.rank > result.lowest_verified_offer.rank


def test_availability_tie_break_prefers_in_stock() -> None:
    result = _compare(
        offer(
            offer_id="limited",
            displayed_price="800.00",
            availability=AvailabilityStatus.LIMITED_STOCK,
            retailer_slug="fictional-mart-a",
        ),
        offer(
            offer_id="in-stock",
            displayed_price="800.00",
            availability=AvailabilityStatus.IN_STOCK,
            retailer_slug="fictional-mart-b",
            retailer_id=RETAILER_B,
        ),
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "in-stock"
    assert result.ranking.criterion is RankingCriterion.AVAILABILITY


def test_seller_quality_tie_break_prefers_first_party() -> None:
    result = _compare(
        offer(
            offer_id="third-party",
            displayed_price="800.00",
            seller_info=seller(first_party=False, active=True),
            retailer_slug="fictional-mart-a",
        ),
        offer(
            offer_id="first-party",
            displayed_price="800.00",
            seller_info=seller(first_party=True, active=True),
            retailer_slug="fictional-mart-b",
            retailer_id=RETAILER_B,
        ),
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "first-party"
    assert result.ranking.criterion is RankingCriterion.SELLER_QUALITY


def test_delivery_information_tie_break_prefers_known_fee() -> None:
    result = _compare(
        offer(
            offer_id="unknown-delivery",
            displayed_price="800.00",
            delivery_fee=None,
            seller_info=seller(first_party=True),
            retailer_slug="fictional-mart-a",
        ),
        offer(
            offer_id="known-delivery",
            displayed_price="800.00",
            delivery_fee="0.00",
            seller_info=seller(first_party=True),
            retailer_slug="fictional-mart-b",
            retailer_id=RETAILER_B,
        ),
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "known-delivery"
    assert result.lowest_verified_offer.effective_price == Decimal("800.00")
    assert result.ranking.criterion is RankingCriterion.DELIVERY


def test_displayed_price_fallback_when_verified_effective_prices_tie() -> None:
    result = _compare(
        offer(
            offer_id="higher-displayed",
            displayed_price="900.00",
            seller_info=seller(first_party=True),
            retailer_slug="fictional-mart-a",
        ),
        offer(
            offer_id="lower-displayed",
            displayed_price="850.00",
            delivery_fee="50.00",
            seller_info=seller(first_party=True),
            retailer_slug="fictional-mart-b",
            retailer_id=RETAILER_B,
        ),
    )
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.effective_price == Decimal("900.00")
    assert result.lowest_verified_offer.offer_id == "lower-displayed"
    assert result.ranking.criterion is RankingCriterion.DISPLAYED_PRICE


def test_no_offers_has_explainable_empty_ranking() -> None:
    result = engine().compare_variant(VARIANT_A, [])
    assert result.lowest_verified_offer is None
    assert result.ranking.criterion is RankingCriterion.NO_APPLICABLE_OFFER
    assert result.offers == ()
    assert result.offer_count == 0
    assert result.distinct_retailer_count == 0
    assert result.displayed_price_min is None
    assert result.displayed_price_max is None


def test_one_retailer_is_returned() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [offer(offer_id="only", displayed_price="500.00")],
    )
    assert len(result.offers) == 1
    assert result.lowest_verified_offer is not None
    assert result.lowest_verified_offer.offer_id == "only"


def test_four_and_ten_retailers_are_not_capped_at_three() -> None:
    four = [
        offer(
            offer_id=f"four-{index}",
            retailer_id=uuid4(),
            retailer_slug=f"fictional-mart-{index}",
            retailer_name=f"Fictional Mart {index}",
            displayed_price=f"{900 + index}.00",
        )
        for index in range(4)
    ]
    ten = [
        offer(
            offer_id=f"ten-{index}",
            retailer_id=uuid4(),
            retailer_slug=f"fictional-mart-ten-{index}",
            retailer_name=f"Fictional Mart Ten {index}",
            displayed_price=f"{800 + index}.00",
        )
        for index in range(10)
    ]
    four_result = engine().compare_variant(VARIANT_A, four)
    ten_result = engine().compare_variant(VARIANT_A, ten)
    assert len(four_result.offers) == 4
    assert four_result.offer_count == 4
    assert four_result.distinct_retailer_count == 4
    assert four_result.displayed_price_min == Decimal("900.00")
    assert four_result.displayed_price_max == Decimal("903.00")
    assert len(ten_result.offers) == 10
    assert ten_result.offer_count == 10
    assert ten_result.distinct_retailer_count == 10
    assert {item.offer_id for item in four_result.offers} == {f"four-{index}" for index in range(4)}
    assert {item.offer_id for item in ten_result.offers} == {f"ten-{index}" for index in range(10)}
    assert {item.rank for item in ten_result.offers} == set(range(1, 11))


def test_two_sellers_on_one_retailer_are_two_offers_not_two_retailers() -> None:
    result = engine().compare_variant(
        VARIANT_A,
        [
            offer(
                offer_id="first-party",
                retailer_id=RETAILER_A,
                retailer_slug="fictional-mart-a",
                displayed_price="1000.00",
                seller_info=seller(name="First Party", first_party=True),
            ),
            offer(
                offer_id="marketplace",
                retailer_id=RETAILER_A,
                retailer_slug="fictional-mart-a",
                displayed_price="980.00",
                seller_info=seller(name="Marketplace Seller"),
            ),
            offer(
                offer_id="other-store",
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
                displayed_price="1100.00",
            ),
        ],
    )
    assert len(result.offers) == 3
    assert result.offer_count == 3
    assert result.distinct_retailer_count == 2
    assert result.displayed_price_min == Decimal("980.00")
    assert result.displayed_price_max == Decimal("1100.00")
    assert {item.retailer_slug for item in result.offers} == {
        "fictional-mart-a",
        "fictional-mart-b",
    }
    assert {item.seller.name for item in result.offers} == {
        "First Party",
        "Marketplace Seller",
        "Fictional Seller",
    }
