"""Monthly price intelligence derived from stored qualifying observations."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.pricing.config import PricingConfig
from app.pricing.enums import MetricStatus, ValueKind
from app.pricing.monthly import compute_monthly_intelligence
from tests.unit.pricing.helpers import NOW, RETAILER_A, RETAILER_B, history_point


def _config() -> PricingConfig:
    return PricingConfig(
        _env_file=None,
        min_observations_for_monthly=3,
        min_months_for_best_buying_month=2,
    )


def test_monthly_aggregation_and_best_buying_month() -> None:
    product_id = uuid4()
    listing = uuid4()
    points = []
    for day in (5, 12, 20):
        points.append(
            history_point(
                product_id=product_id,
                listing_id=listing,
                displayed_price="100.00",
                observed_at=NOW.replace(year=2025, month=1, day=day),
            )
        )
        points.append(
            history_point(
                product_id=product_id,
                listing_id=listing,
                displayed_price="180.00",
                observed_at=NOW.replace(year=2025, month=2, day=day),
            )
        )
    result = compute_monthly_intelligence(points, as_of=NOW, config=_config())
    january = result.months[0]
    february = result.months[1]
    assert january.month_name == "January"
    assert january.median.status is MetricStatus.AVAILABLE
    assert january.median.value == Decimal("100.00")
    assert january.minimum.value == Decimal("100.00")
    assert january.maximum.value == Decimal("100.00")
    assert january.average.value == Decimal("100.00")
    assert january.observation_count == 3
    assert january.historical_low.value == Decimal("100.00")
    assert january.historical_high.value == Decimal("100.00")
    assert february.median.value == Decimal("180.00")
    assert result.best_buying_month is not None
    assert result.best_buying_month.month == 1
    assert result.best_buying_month_price.status is MetricStatus.AVAILABLE
    assert result.best_buying_month_price.value == Decimal("100.00")
    assert result.best_buying_month_price.value_kind is ValueKind.CALCULATED
    assert result.predicted is None
    march = result.months[2]
    assert march.median.status is MetricStatus.INSUFFICIENT_HISTORY
    assert march.median.value is None


def test_monthly_insufficient_data_is_not_invented() -> None:
    product_id = uuid4()
    points = [
        history_point(
            product_id=product_id,
            displayed_price="50.00",
            observed_at=NOW - timedelta(days=10),
        )
    ]
    result = compute_monthly_intelligence(points, as_of=NOW, config=_config())
    assert result.best_buying_month is None
    assert result.best_buying_month_price.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.best_buying_month_price.value is None
    for bucket in result.months:
        assert bucket.median.value is None
        assert bucket.median.status is MetricStatus.INSUFFICIENT_HISTORY


def test_unverified_observations_are_excluded_from_monthly_stats() -> None:
    from app.domain.enums import ConfidenceLevel

    product_id = uuid4()
    listing = uuid4()
    points = [
        history_point(
            product_id=product_id,
            listing_id=listing,
            displayed_price="10.00",
            confidence=ConfidenceLevel.LOW,
            observed_at=NOW.replace(year=2025, month=3, day=1),
        ),
        history_point(
            product_id=product_id,
            listing_id=listing,
            displayed_price="20.00",
            confidence=ConfidenceLevel.LOW,
            observed_at=NOW.replace(year=2025, month=3, day=2),
        ),
        history_point(
            product_id=product_id,
            listing_id=listing,
            displayed_price="30.00",
            confidence=ConfidenceLevel.LOW,
            observed_at=NOW.replace(year=2025, month=3, day=3),
        ),
    ]
    result = compute_monthly_intelligence(points, as_of=NOW, config=_config())
    assert result.qualifying_observation_count == 0
    assert result.months[2].observation_count == 0
    assert result.months[2].median.value is None


def test_retailer_specific_monthly_buckets_stay_separate() -> None:
    product_id = uuid4()
    points = []
    for day in (4, 11, 18):
        points.append(
            history_point(
                product_id=product_id,
                retailer_id=RETAILER_A,
                retailer_slug="fictional-mart-a",
                retailer_name="Fictional Mart A",
                displayed_price="90.00",
                observed_at=NOW.replace(year=2025, month=4, day=day),
            )
        )
        points.append(
            history_point(
                product_id=product_id,
                retailer_id=RETAILER_B,
                retailer_slug="fictional-mart-b",
                retailer_name="Fictional Mart B",
                displayed_price="140.00",
                observed_at=NOW.replace(year=2025, month=4, day=day),
            )
        )
    result = compute_monthly_intelligence(points, as_of=NOW, config=_config())
    april = result.months[3]
    assert april.median.status is MetricStatus.AVAILABLE
    by_retailer = {(item.retailer_id, item.month): item for item in result.retailer_months}
    assert by_retailer[(RETAILER_A, 4)].median.value == Decimal("90.00")
    assert by_retailer[(RETAILER_B, 4)].median.value == Decimal("140.00")
