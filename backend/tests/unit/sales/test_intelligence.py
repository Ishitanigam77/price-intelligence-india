"""Sale-timing intelligence: current vs expected retailers, savings, major vs ordinary."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.enums import SaleEventType, SaleEvidenceStatus, SaleSeverity
from app.pricing.engine import PriceComparisonEngine
from app.pricing.enums import MetricStatus, ValueKind
from app.sales.intelligence import SaleIntelligenceEngine, expected_savings
from app.sales.timing_models import TIMING_DISCLAIMER, ListingPredictionInput
from tests.unit.pricing.helpers import offer
from tests.unit.sales.helpers import (
    PRODUCT_ID,
    RETAILER_A,
    RETAILER_B,
    VARIANT_A,
    event_record,
    observation,
    sales_config,
)

AS_OF = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _comparison(offers):
    engine = PriceComparisonEngine(clock=lambda: AS_OF)
    return engine.compare_variant(VARIANT_A, offers, variant_key="color=black|storage=128gb")


def test_expected_savings_never_negative() -> None:
    assert expected_savings(Decimal("50000.00"), Decimal("43000.00")) == (
        Decimal("7000.00"),
        Decimal("14.00"),
    )
    assert expected_savings(Decimal("100.00"), Decimal("120.00")) == (None, None)
    assert expected_savings(None, Decimal("80.00")) == (None, None)
    assert expected_savings(Decimal("100.00"), None) == (None, None)
    assert expected_savings(Decimal("0"), Decimal("1.00")) == (None, None)


def test_current_cheapest_is_not_assumed_future_cheapest() -> None:
    offers = [
        offer(
            offer_id="a",
            variant_id=VARIANT_A,
            retailer_id=RETAILER_A,
            retailer_slug="fictional-mart-a",
            retailer_name="Fictional Mart A",
            displayed_price="50000.00",
            source_effective_price="50000.00",
        ),
        offer(
            offer_id="b",
            variant_id=VARIANT_A,
            retailer_id=RETAILER_B,
            retailer_slug="fictional-mart-b",
            retailer_name="Fictional Mart B",
            displayed_price="49500.00",
            source_effective_price="49500.00",
        ),
    ]
    events = [
        event_record(
            name="FIXTURE: Major Sale 2024",
            event_type=SaleEventType.SEASONAL,
            start_date=datetime(2024, 10, 21, tzinfo=UTC),
            end_date=datetime(2024, 10, 28, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Major Sale 2025",
            event_type=SaleEventType.SEASONAL,
            start_date=datetime(2025, 10, 10, tzinfo=UTC),
            end_date=datetime(2025, 10, 17, tzinfo=UTC),
        ),
    ]
    points = []
    starts = (
        datetime(2024, 10, 21, tzinfo=UTC),
        datetime(2025, 10, 10, tzinfo=UTC),
    )
    for start in starts:
        points.append(
            observation(
                retailer_id=RETAILER_A,
                displayed_price="60000.00",
                effective_price="60000.00",
                observed_at=start - timedelta(days=5),
            )
        )
        points.append(
            observation(
                retailer_id=RETAILER_A,
                displayed_price="43500.00",
                effective_price="43500.00",
                observed_at=start + timedelta(days=1),
            )
        )
        points.append(
            observation(
                retailer_id=RETAILER_B,
                displayed_price="59000.00",
                effective_price="59000.00",
                observed_at=start - timedelta(days=5),
            )
        )
        points.append(
            observation(
                retailer_id=RETAILER_B,
                displayed_price="45000.00",
                effective_price="45000.00",
                observed_at=start + timedelta(days=1),
            )
        )
    predictions = [
        ListingPredictionInput(
            retailer_id=RETAILER_A,
            status="PREDICTED",
            predicted_price=Decimal("43500.00"),
            lower_bound=Decimal("42000.00"),
            upper_bound=Decimal("45000.00"),
            confidence=0.82,
        ),
        ListingPredictionInput(
            retailer_id=RETAILER_B,
            status="PREDICTED",
            predicted_price=Decimal("45000.00"),
            lower_bound=Decimal("44000.00"),
            upper_bound=Decimal("46000.00"),
            confidence=0.70,
        ),
    ]
    result = SaleIntelligenceEngine(config=sales_config()).compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        variant_key="color=black|storage=128gb",
        comparison=_comparison(offers),
        events=events,
        points=points,
        predictions=predictions,
        as_of=AS_OF,
    )
    assert result.current_cheapest_retailer_id == RETAILER_B
    assert result.current_cheapest_price == Decimal("49500.00")
    assert result.expected_best_retailer is not None
    assert result.expected_best_retailer.retailer_id == RETAILER_A
    assert result.expected_best_retailer.expected_sale_price == Decimal("43500.00")
    assert result.expected_best_retailer.expected_sale_price_value_kind is ValueKind.PREDICTED
    assert result.expected_best_retailer.expected_saving == Decimal("6500.00")
    assert result.disclaimer == TIMING_DISCLAIMER


def test_insufficient_retailer_evidence_is_unknown() -> None:
    offers = [
        offer(
            offer_id="a",
            variant_id=VARIANT_A,
            retailer_id=RETAILER_A,
            displayed_price="50000.00",
            source_effective_price="50000.00",
        )
    ]
    result = SaleIntelligenceEngine(config=sales_config()).compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        variant_key=None,
        comparison=_comparison(offers),
        events=(),
        points=(),
        predictions=(),
        as_of=AS_OF,
    )
    assert result.expected_best_retailer is None
    assert result.ordinary is None
    assert result.major is None
    assert result.current_cheapest_retailer_id == RETAILER_A


def test_major_vs_ordinary_comparison_uses_expected_prices() -> None:
    offers = [
        offer(
            offer_id="a",
            variant_id=VARIANT_A,
            retailer_id=RETAILER_A,
            displayed_price="50000.00",
            source_effective_price="50000.00",
        )
    ]
    events = [
        event_record(
            name="FIXTURE: Ordinary Promo 2024",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=datetime(2024, 2, 1, tzinfo=UTC),
            end_date=datetime(2024, 2, 2, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Ordinary Promo 2025",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=datetime(2025, 2, 1, tzinfo=UTC),
            end_date=datetime(2025, 2, 2, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Major Sale 2024",
            event_type=SaleEventType.SEASONAL,
            start_date=datetime(2024, 10, 21, tzinfo=UTC),
            end_date=datetime(2024, 10, 28, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Major Sale 2025",
            event_type=SaleEventType.SEASONAL,
            start_date=datetime(2025, 10, 10, tzinfo=UTC),
            end_date=datetime(2025, 10, 17, tzinfo=UTC),
        ),
    ]
    points = []
    for start, sale_price in (
        (datetime(2024, 2, 1, tzinfo=UTC), "47500.00"),
        (datetime(2025, 2, 1, tzinfo=UTC), "47500.00"),
        (datetime(2024, 10, 21, tzinfo=UTC), "43000.00"),
        (datetime(2025, 10, 10, tzinfo=UTC), "43000.00"),
    ):
        points.append(
            observation(
                displayed_price="50000.00",
                effective_price="50000.00",
                observed_at=start - timedelta(days=4),
            )
        )
        points.append(
            observation(
                displayed_price=sale_price,
                effective_price=sale_price,
                observed_at=start + timedelta(hours=12),
            )
        )
    result = SaleIntelligenceEngine(config=sales_config()).compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        variant_key=None,
        comparison=_comparison(offers),
        events=events,
        points=points,
        predictions=(),
        as_of=AS_OF,
    )
    assert result.ordinary is not None
    assert result.major is not None
    assert result.ordinary.status is MetricStatus.AVAILABLE
    assert result.major.status is MetricStatus.AVAILABLE
    assert result.ordinary.expected_price == Decimal("47500.00")
    assert result.major.expected_price == Decimal("43000.00")
    assert result.ordinary.expected_saving == Decimal("2500.00")
    assert result.major.expected_saving == Decimal("7000.00")
    assert result.ordinary.sale_type is SaleSeverity.ORDINARY
    assert result.major.sale_type is SaleSeverity.MAJOR
    assert result.ordinary.window.evidence_status is not SaleEvidenceStatus.CONFIRMED
    assert result.major.days_until_start is not None
    assert result.ordinary.days_until_start is not None
    assert result.major.days_until_start > result.ordinary.days_until_start


def test_missing_prediction_falls_back_to_historical_median() -> None:
    offers = [
        offer(
            offer_id="a",
            variant_id=VARIANT_A,
            retailer_id=RETAILER_A,
            displayed_price="1000.00",
            source_effective_price="1000.00",
        )
    ]
    events = [
        event_record(
            name="FIXTURE: Recurring 2024",
            start_date=datetime(2024, 5, 1, tzinfo=UTC),
            end_date=datetime(2024, 5, 4, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Recurring 2025",
            start_date=datetime(2025, 5, 1, tzinfo=UTC),
            end_date=datetime(2025, 5, 4, tzinfo=UTC),
        ),
    ]
    points = [
        observation(
            displayed_price="800.00",
            effective_price="800.00",
            observed_at=datetime(2024, 5, 2, tzinfo=UTC),
        ),
        observation(
            displayed_price="820.00",
            effective_price="820.00",
            observed_at=datetime(2025, 5, 2, tzinfo=UTC),
        ),
    ]
    result = SaleIntelligenceEngine(config=sales_config()).compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        variant_key=None,
        comparison=_comparison(offers),
        events=events,
        points=points,
        predictions=[
            ListingPredictionInput(
                retailer_id=RETAILER_A,
                status="INSUFFICIENT_DATA",
                predicted_price=None,
                confidence=None,
            )
        ],
        as_of=AS_OF,
    )
    assert result.ordinary is not None or result.major is not None
    opportunity = result.major or result.ordinary
    assert opportunity is not None
    assert opportunity.expected_price_value_kind is ValueKind.CALCULATED
    assert opportunity.expected_price is not None
