"""Builders for recommendation unit tests. All data is fictional fixture data."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.enums import ConfidenceLevel, SaleEventSource, SaleEventStatus
from app.pricing.enums import FreshnessStatus, MetricStatus, TrendDirection, ValueKind
from app.recommendation.config import RecommendationConfig
from app.recommendation.engine import RecommendationEngine
from app.recommendation.models import (
    OptionalMetric,
    PredictionInput,
    RecommendationInput,
    UpcomingSaleInput,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
PRODUCT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
VARIANT_A = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
RETAILER_A = UUID("11111111-1111-1111-1111-111111111111")


def rec_config(**overrides: object) -> RecommendationConfig:
    return RecommendationConfig(_env_file=None, **overrides)


def engine(config: RecommendationConfig | None = None) -> RecommendationEngine:
    return RecommendationEngine(config=config or rec_config(), clock=lambda: NOW)


def calculated(
    value: Decimal | str | None,
    *,
    unit: str = "INR",
    status: MetricStatus = MetricStatus.AVAILABLE,
    count: int = 10,
    window_days: int | None = None,
) -> OptionalMetric:
    amount: Decimal | None
    if value is None:
        amount = None
        status = MetricStatus.INSUFFICIENT_HISTORY
    elif isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(value)
    return OptionalMetric(
        value=amount,
        value_kind=ValueKind.CALCULATED,
        status=status,
        unit=unit,
        observation_count=count,
        window_days=window_days,
    )


def prediction(
    *,
    price: Decimal | str | None = "80.00",
    confidence: float | None = 0.80,
    status: str = "PREDICTED",
    reason: str | None = None,
) -> PredictionInput:
    amount = None if price is None else Decimal(price) if not isinstance(price, Decimal) else price
    return PredictionInput(
        status=status,
        predicted_price=amount,
        confidence=confidence,
        insufficient_reason=reason,
        product_variant_id=VARIANT_A,
        retailer_id=RETAILER_A,
        seller_id=None,
        model_version="fixture-not-a-trained-model",
    )


def upcoming(
    *,
    name: str = "FIXTURE: Fictional Seasonal Sale",
    days: int = 7,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    source: SaleEventSource = SaleEventSource.MANUAL_CURATION,
    status: SaleEventStatus = SaleEventStatus.BEFORE_EVENT,
) -> UpcomingSaleInput:
    start = NOW + timedelta(days=days)
    return UpcomingSaleInput(
        event_id=uuid4(),
        name=name,
        start_date=start,
        end_date=start + timedelta(days=5),
        confidence=confidence,
        source=source,
        status=status,
        days_until_start=days,
    )


def payload(**overrides: object) -> RecommendationInput:
    """Neutral, complete, fictional history. Override fields per test."""
    values: dict[str, object] = {
        "as_of": NOW,
        "product_id": PRODUCT_ID,
        "product_variant_id": VARIANT_A,
        "currency": "INR",
        "current_effective_price": Decimal("150.00"),
        "current_price_value_kind": ValueKind.CALCULATED,
        "current_price_field": "effective_price",
        "qualifying_observation_count": 10,
        "freshness_status": FreshnessStatus.FRESH,
        "historical_percentile": calculated("45.00", unit="percentile"),
        "historical_low": calculated("100.00"),
        "average_30d": calculated("148.00", window_days=30),
        "average_90d": calculated("152.00", window_days=90),
        "trend_direction": TrendDirection.STABLE,
        "prediction": None,
        "upcoming_events": (),
    }
    values.update(overrides)
    return RecommendationInput(**values)  # type: ignore[arg-type]
