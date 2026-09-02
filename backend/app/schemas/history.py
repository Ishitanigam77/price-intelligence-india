"""API schemas for `GET /api/v1/products/{product_id}/history`.

Observed snapshots, calculated aggregates, and (absent) predictions are kept as separate
fields. A missing calculation is `insufficient_history` with an explicit reason — never a
fabricated zero or synthetic observation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.pricing.enums import InsufficientReasonCode, MetricStatus, TrendDirection, ValueKind
from app.pricing.history_models import (
    CalculatedMetric,
    ExtremaMetric,
    HistoricalObservationPoint,
    HistoryProvenance,
    MonthlyBucket,
    MonthlyPriceIntelligence,
    ProductHistory,
    VariantHistory,
)
from app.schemas.common import Page
from app.schemas.comparison import DataFreshnessRead


class InsufficientHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: InsufficientReasonCode
    reason: str


class CalculatedMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus
    value: Decimal | None = None
    unit: str
    window_days: int | None = None
    observation_count: int
    calculated_at: datetime
    insufficient: InsufficientHistoryRead | None = None
    extra: dict[str, Decimal | int | str | None] = Field(default_factory=dict)


class ExtremaMetricRead(CalculatedMetricRead):
    snapshot_id: uuid.UUID | None = None
    observed_at: datetime | None = None
    retailer_id: uuid.UUID | None = None
    seller_id: uuid.UUID | None = None
    source_url: str | None = None


class PriceDropRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus
    drop_occurred: bool | None = None
    percentage_change: Decimal | None = None
    current_price: Decimal | None = None
    baseline_price: Decimal | None = None
    current_observed_at: datetime | None = None
    baseline_observed_at: datetime | None = None
    current_snapshot_id: uuid.UUID | None = None
    baseline_snapshot_id: uuid.UUID | None = None
    baseline_retailer_id: uuid.UUID | None = None
    baseline_seller_id: uuid.UUID | None = None
    baseline_description: str
    observation_count: int
    calculated_at: datetime
    insufficient: InsufficientHistoryRead | None = None


class TrendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus
    direction: TrendDirection
    implied_percent_change: Decimal | None = None
    slope_per_day: Decimal | None = None
    method: str
    observation_count: int
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    calculated_at: datetime
    insufficient: InsufficientHistoryRead | None = None


class HistoryProvenanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observations_value_kind: Literal[ValueKind.OBSERVED] = ValueKind.OBSERVED
    calculations_value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    predicted: None = None
    predicted_value_kind: None = None
    analysis_price_rule: str
    price_drop_baseline: str
    trend_method: str


class HistoryObservationRead(BaseModel):
    """One stored price observation. `value_kind` is always OBSERVED."""

    model_config = ConfigDict(from_attributes=True)

    value_kind: Literal[ValueKind.OBSERVED] = ValueKind.OBSERVED
    id: uuid.UUID
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_slug: str
    retailer_name: str
    retailer_product_id: uuid.UUID
    seller_id: uuid.UUID | None = None
    source_url: str | None = None
    source_type: SourceType
    observed_at: datetime
    created_at: datetime
    currency: str
    displayed_price: Decimal
    effective_price: Decimal | None = None
    effective_price_value_kind: Literal[ValueKind.CALCULATED] | None = None
    mrp: Decimal | None = None
    analysis_price: Decimal
    analysis_price_field: Literal["effective_price", "displayed_price"]
    availability: AvailabilityStatus
    confidence: ConfidenceLevel
    qualifies_for_calculations: bool


class MonthlyBucketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: int
    month_name: str
    retailer_id: uuid.UUID | None = None
    retailer_slug: str | None = None
    retailer_name: str | None = None
    years_used: list[int]
    observation_count: int
    minimum: CalculatedMetricRead
    average: CalculatedMetricRead
    median: CalculatedMetricRead
    maximum: CalculatedMetricRead
    historical_low: CalculatedMetricRead
    historical_high: CalculatedMetricRead
    volatility: CalculatedMetricRead


class MonthlyPriceIntelligenceRead(BaseModel):
    """CALCULATED month-of-year view. Does not replace rolling 7/30/90/180-day windows."""

    model_config = ConfigDict(from_attributes=True)

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    months: list[MonthlyBucketRead]
    retailer_months: list[MonthlyBucketRead] = Field(default_factory=list)
    best_buying_month: MonthlyBucketRead | None = None
    best_buying_month_price: CalculatedMetricRead
    qualifying_observation_count: int
    calculated_at: datetime
    method: str
    predicted: None = None


class VariantHistoryRead(BaseModel):
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    variant_key: str | None = None
    observations: Page[HistoryObservationRead]
    qualifying_observation_count: int
    excluded_unverified_observation_count: int
    current_observation: HistoryObservationRead | None = None
    average_7d: CalculatedMetricRead
    average_30d: CalculatedMetricRead
    average_90d: CalculatedMetricRead
    average_180d: CalculatedMetricRead
    historical_low: ExtremaMetricRead
    historical_high: ExtremaMetricRead
    current_price_percentile: CalculatedMetricRead
    volatility: CalculatedMetricRead
    percentage_change: CalculatedMetricRead
    price_drop: PriceDropRead
    trend: TrendRead
    monthly: MonthlyPriceIntelligenceRead
    data_freshness: DataFreshnessRead
    provenance: HistoryProvenanceRead
    calculated_at: datetime


class ProductHistoryRead(BaseModel):
    """Response for `GET /api/v1/products/{product_id}/history`."""

    product_id: uuid.UUID
    variants: list[VariantHistoryRead]
    data_freshness: DataFreshnessRead
    provenance: HistoryProvenanceRead
    calculated_at: datetime
    predicted: None = None


def _metric_read(metric: CalculatedMetric) -> CalculatedMetricRead:
    return CalculatedMetricRead.model_validate(metric)


def _extrema_read(metric: ExtremaMetric) -> ExtremaMetricRead:
    return ExtremaMetricRead.model_validate(metric)


def _observation_read(point: HistoricalObservationPoint) -> HistoryObservationRead:
    return HistoryObservationRead(
        value_kind=ValueKind.OBSERVED,
        id=point.snapshot_id,
        product_id=point.product_id,
        product_variant_id=point.product_variant_id,
        retailer_id=point.retailer_id,
        retailer_slug=point.retailer_slug,
        retailer_name=point.retailer_name,
        retailer_product_id=point.retailer_product_id,
        seller_id=point.seller_id,
        source_url=point.source_url,
        source_type=point.source_type,
        observed_at=point.observed_at,
        created_at=point.created_at,
        currency=point.currency,
        displayed_price=point.displayed_price,
        effective_price=point.effective_price,
        effective_price_value_kind=(
            ValueKind.CALCULATED if point.effective_price is not None else None
        ),
        mrp=point.mrp,
        analysis_price=point.analysis_price,
        analysis_price_field=point.analysis_price_field,
        availability=point.availability,
        confidence=point.confidence,
        qualifies_for_calculations=point.qualifies_for_calculations,
    )


def _provenance_read(provenance: HistoryProvenance) -> HistoryProvenanceRead:
    return HistoryProvenanceRead.model_validate(provenance)


def _monthly_bucket_read(bucket: MonthlyBucket) -> MonthlyBucketRead:
    return MonthlyBucketRead(
        month=bucket.month,
        month_name=bucket.month_name,
        retailer_id=bucket.retailer_id,
        retailer_slug=bucket.retailer_slug,
        retailer_name=bucket.retailer_name,
        years_used=list(bucket.years_used),
        observation_count=bucket.observation_count,
        minimum=_metric_read(bucket.minimum),
        average=_metric_read(bucket.average),
        median=_metric_read(bucket.median),
        maximum=_metric_read(bucket.maximum),
        historical_low=_metric_read(bucket.historical_low),
        historical_high=_metric_read(bucket.historical_high),
        volatility=_metric_read(bucket.volatility),
    )


def _monthly_read(monthly: MonthlyPriceIntelligence) -> MonthlyPriceIntelligenceRead:
    return MonthlyPriceIntelligenceRead(
        value_kind=ValueKind.CALCULATED,
        months=[_monthly_bucket_read(item) for item in monthly.months],
        retailer_months=[_monthly_bucket_read(item) for item in monthly.retailer_months],
        best_buying_month=(
            _monthly_bucket_read(monthly.best_buying_month)
            if monthly.best_buying_month is not None
            else None
        ),
        best_buying_month_price=_metric_read(monthly.best_buying_month_price),
        qualifying_observation_count=monthly.qualifying_observation_count,
        calculated_at=monthly.calculated_at,
        method=monthly.method,
        predicted=None,
    )


def variant_history_read(
    variant: VariantHistory,
    observations: Page[HistoricalObservationPoint],
) -> VariantHistoryRead:
    return VariantHistoryRead(
        product_id=variant.product_id,
        product_variant_id=variant.product_variant_id,
        variant_key=variant.variant_key,
        observations=Page[HistoryObservationRead](
            items=[_observation_read(item) for item in observations.items],
            total=observations.total,
            limit=observations.limit,
            offset=observations.offset,
        ),
        qualifying_observation_count=variant.qualifying_observation_count,
        excluded_unverified_observation_count=variant.excluded_unverified_observation_count,
        current_observation=(
            _observation_read(variant.current_observation)
            if variant.current_observation is not None
            else None
        ),
        average_7d=_metric_read(variant.average_7d),
        average_30d=_metric_read(variant.average_30d),
        average_90d=_metric_read(variant.average_90d),
        average_180d=_metric_read(variant.average_180d),
        historical_low=_extrema_read(variant.historical_low),
        historical_high=_extrema_read(variant.historical_high),
        current_price_percentile=_metric_read(variant.current_price_percentile),
        volatility=_metric_read(variant.volatility),
        percentage_change=_metric_read(variant.percentage_change),
        price_drop=PriceDropRead.model_validate(variant.price_drop),
        trend=TrendRead.model_validate(variant.trend),
        monthly=_monthly_read(variant.monthly),
        data_freshness=DataFreshnessRead.model_validate(variant.data_freshness),
        provenance=_provenance_read(variant.provenance),
        calculated_at=variant.calculated_at,
    )


def product_history_read(
    history: ProductHistory,
    observation_pages: dict[uuid.UUID, Page[HistoricalObservationPoint]],
) -> ProductHistoryRead:
    return ProductHistoryRead(
        product_id=history.product_id,
        variants=[
            variant_history_read(
                variant,
                observation_pages.get(
                    variant.product_variant_id,
                    Page[HistoricalObservationPoint](items=[], total=0, limit=1, offset=0),
                ),
            )
            for variant in history.variants
        ],
        data_freshness=DataFreshnessRead.model_validate(history.data_freshness),
        provenance=_provenance_read(history.provenance),
        calculated_at=history.calculated_at,
        predicted=None,
    )
