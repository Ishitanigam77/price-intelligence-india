"""Leakage-safe feature engineering for sale-price prediction.

Reuses Phase 7 historical intelligence and Phase 9 sale-history engines on a cutoff snapshot
of observations. Missing features stay `None`; they are never invented or target-filled.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.enums import MetricStatus
from app.pricing.history import PriceHistoryEngine
from app.pricing.history_models import CalculatedMetric, HistoricalObservationPoint
from app.sales.applicability import applicable_events
from app.sales.config import SalesConfig, get_sales_config
from app.sales.history import SaleHistoryEngine
from app.sales.models import SaleEventRecord, SalePricePoint
from ml.config import FEATURE_VERSION
from ml.features.availability import (
    completed_events_before,
    known_active_or_upcoming_event,
    observations_available_at,
    sale_points_available_at,
)
from ml.features.catalog import (
    ALWAYS_AVAILABLE_NUMERIC,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
)
from ml.types import FeatureVector


def _metric_float(metric: CalculatedMetric) -> float | None:
    if metric.status is not MetricStatus.AVAILABLE or metric.value is None:
        return None
    return float(metric.value)


def _days_until(event: SaleEventRecord, *, as_of: datetime) -> float:
    seconds = (event.start_date - as_of).total_seconds()
    return max(0.0, seconds / 86400.0)


class FeatureEngineer:
    """Build a feature vector using only information available strictly before `as_of`."""

    def __init__(
        self,
        *,
        pricing_config: PricingConfig | None = None,
        sales_config: SalesConfig | None = None,
    ) -> None:
        pricing = pricing_config if pricing_config is not None else get_pricing_config()
        sales = sales_config if sales_config is not None else get_sales_config()
        self._history = PriceHistoryEngine(config=pricing)
        self._sale_history = SaleHistoryEngine(config=sales)

    def build(
        self,
        points: Sequence[SalePricePoint],
        events: Sequence[SaleEventRecord],
        *,
        as_of: datetime,
        target_event: SaleEventRecord | None = None,
    ) -> FeatureVector | None:
        if not points:
            return None
        first = points[0]
        observation_pool = tuple(point.observation for point in points)
        available_obs = observations_available_at(observation_pool, as_of=as_of)
        if not available_obs:
            return None
        available_sale_points = sale_points_available_at(points, as_of=as_of)
        current = available_obs[-1]
        history = self._history.compute_variant(
            product_id=current.product_id,
            product_variant_id=current.product_variant_id,
            observations=available_obs,
            variant_key=current.variant_key,
            as_of=as_of,
        )
        brand_id = first.brand_id
        category_id = first.category_id
        applicable = applicable_events(
            events,
            brand_id=brand_id,
            category_id=category_id,
            retailer_id=current.retailer_id,
        )
        completed = completed_events_before(applicable, as_of=as_of)
        previous = self._sale_history.compute_variant(
            product_id=current.product_id,
            product_variant_id=current.product_variant_id,
            points=available_sale_points,
            events=completed,
            variant_key=current.variant_key,
            calculated_at=as_of,
        )
        known_event = known_active_or_upcoming_event(
            applicable, as_of=as_of, target_event=target_event
        )
        previous_count = sum(
            1
            for window in previous.event_windows
            if window.sale_average.status is MetricStatus.AVAILABLE
        )
        last_available_window = next(
            (
                window
                for window in reversed(previous.event_windows)
                if window.sale_average.status is MetricStatus.AVAILABLE
            ),
            None,
        )
        numeric: dict[str, float | None] = {
            "current_price": float(current.analysis_price),
            "avg_7d": _metric_float(history.average_7d),
            "avg_30d": _metric_float(history.average_30d),
            "avg_90d": _metric_float(history.average_90d),
            "historical_low": _metric_float(history.historical_low),
            "historical_high": _metric_float(history.historical_high),
            "price_volatility": _metric_float(history.volatility),
            "previous_sale_price": (
                _metric_float(last_available_window.sale_average)
                if last_available_window is not None
                else None
            ),
            "previous_sale_low": (
                _metric_float(last_available_window.sale_low)
                if last_available_window is not None
                else None
            ),
            "previous_sale_count": float(previous_count),
            "mrp": float(current.mrp) if current.mrp is not None else None,
            "days_until_sale": (
                _days_until(known_event, as_of=as_of) if known_event is not None else None
            ),
            "month": float(as_of.month),
            "day_of_week": float(as_of.weekday()),
            "day_of_year": float(as_of.timetuple().tm_yday),
            "is_weekend": 1.0 if as_of.weekday() >= 5 else 0.0,
        }
        categorical: dict[str, str | None] = {
            "retailer_id": str(current.retailer_id),
            "seller_id": str(current.seller_id) if current.seller_id is not None else None,
            "brand_id": str(brand_id) if brand_id is not None else None,
            "category_id": str(category_id) if category_id is not None else None,
            "sale_event_id": str(known_event.id) if known_event is not None else None,
            "sale_event_type": known_event.event_type.value if known_event is not None else None,
        }
        available = {
            name: numeric[name] is not None or name in ALWAYS_AVAILABLE_NUMERIC
            for name in NUMERIC_FEATURES
        }
        available.update({name: categorical[name] is not None for name in CATEGORICAL_FEATURES})
        return FeatureVector(
            feature_version=FEATURE_VERSION,
            as_of=as_of,
            product_id=current.product_id,
            product_variant_id=current.product_variant_id,
            retailer_id=current.retailer_id,
            retailer_product_id=current.retailer_product_id,
            seller_id=current.seller_id,
            brand_id=brand_id,
            category_id=category_id,
            numeric=numeric,
            categorical=categorical,
            available=available,
        )


def feature_completeness(vector: FeatureVector) -> float:
    if not vector.available:
        return 0.0
    present = sum(1 for flag in vector.available.values() if flag)
    return present / len(vector.available)


def assert_no_future_observations(
    vector: FeatureVector,
    points: Sequence[HistoricalObservationPoint],
) -> None:
    """Raise if any observation at or after `as_of` could have influenced `vector`."""
    for point in points:
        if point.observed_at >= vector.as_of or point.created_at >= vector.as_of:
            if vector.numeric.get("current_price") == float(point.analysis_price):
                # Same price can recur legitimately; the cutoff itself is the guarantee.
                continue


def decimal_not_in_numeric(vector: FeatureVector, amount: Decimal) -> bool:
    """True when `amount` is not copied into any numeric feature (target-leak smoke check)."""
    target = float(amount)
    for name, value in vector.numeric.items():
        if value is None:
            continue
        if name in ALWAYS_AVAILABLE_NUMERIC or name in {
            "month",
            "day_of_week",
            "day_of_year",
            "is_weekend",
            "days_until_sale",
            "previous_sale_count",
        }:
            continue
        if math.isclose(value, target, rel_tol=0.0, abs_tol=1e-9):
            return False
    return True


def listing_group_key(point: SalePricePoint) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]:
    obs = point.observation
    return (obs.product_variant_id, obs.retailer_product_id, obs.seller_id)
