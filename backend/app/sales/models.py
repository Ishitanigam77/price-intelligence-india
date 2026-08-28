"""Retailer-agnostic inputs and outputs of sale-event intelligence.

The engines never see ORM objects or HTTP schemas. Callers project persisted `SaleEvent` rows
and `PriceSnapshot` observations into these records. Calculated statistics are withheld
(never zero-filled) when history is insufficient. Predicted values are not produced.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.domain.enums import (
    ConfidenceLevel,
    SaleEventSource,
    SaleEventStatus,
    SaleEventType,
)
from app.domain.validation import (
    normalize_sale_event_source_ref,
    validate_sale_event,
    validate_sale_event_dates,
)
from app.pricing.enums import MetricStatus, ValueKind
from app.pricing.history_models import HistoricalObservationPoint
from app.sales.enums import SaleInsufficientReasonCode


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class SaleEventRecord(_FrozenModel):
    """One persisted (or detected) sale window as the engines see it."""

    id: uuid.UUID
    name: str
    retailer_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    start_date: datetime
    end_date: datetime
    event_type: SaleEventType
    source: SaleEventSource
    source_ref: str | None = None
    confidence: ConfidenceLevel

    @field_validator("start_date", "end_date")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Sale event dates must be timezone-aware.")
        return value

    @field_validator("name")
    @classmethod
    def _require_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Sale event name must not be blank.")
        return stripped

    @field_validator("source_ref")
    @classmethod
    def _normalize_ref(cls, value: str | None) -> str | None:
        return normalize_sale_event_source_ref(value)

    def model_post_init(self, __context: object) -> None:
        validate_sale_event_dates(self.start_date, self.end_date)
        validate_sale_event(
            event_type=self.event_type,
            source=self.source,
            source_ref=self.source_ref,
            retailer_id=self.retailer_id,
            category_id=self.category_id,
            brand_id=self.brand_id,
            start_date=self.start_date,
            end_date=self.end_date,
        )


class SaleEventView(_FrozenModel):
    """A `SaleEventRecord` with lifecycle status computed at a point in time."""

    event: SaleEventRecord
    status: SaleEventStatus
    as_of: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> uuid.UUID:
        return self.event.id


class SalePricePoint(_FrozenModel):
    """A stored price observation plus optional product brand/category for applicability."""

    observation: HistoricalObservationPoint
    brand_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_kind(self) -> Literal[ValueKind.OBSERVED]:
        return ValueKind.OBSERVED


class SaleInsufficient(_FrozenModel):
    code: SaleInsufficientReasonCode
    reason: str


class SaleCalculatedMetric(_FrozenModel):
    """A derived sale-price statistic. `value` is None when history is insufficient."""

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus
    value: Decimal | None = None
    unit: str
    observation_count: int = Field(ge=0)
    calculated_at: datetime
    insufficient: SaleInsufficient | None = None
    extra: dict[str, Decimal | int | str | None] = Field(default_factory=dict)


class EventWindowHistory(_FrozenModel):
    """Observed prices and calculated stats for one variant during one sale event."""

    event: SaleEventView
    observations: tuple[HistoricalObservationPoint, ...]
    observation_count: int = Field(ge=0)
    sale_average: SaleCalculatedMetric
    sale_low: SaleCalculatedMetric
    sale_high: SaleCalculatedMetric
    vs_non_sale_baseline_percent: SaleCalculatedMetric


class VariantSaleHistory(_FrozenModel):
    """Sale-price history for a single matched product variant. Variants are never mixed."""

    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    variant_key: str | None = None
    event_windows: tuple[EventWindowHistory, ...]
    qualifying_observation_count: int
    excluded_unverified_observation_count: int
    overall_sale_average: SaleCalculatedMetric
    overall_sale_low: SaleCalculatedMetric
    overall_sale_high: SaleCalculatedMetric
    non_sale_baseline: SaleCalculatedMetric
    vs_non_sale_baseline_percent: SaleCalculatedMetric
    calculated_at: datetime


class SaleHistoryProvenance(_FrozenModel):
    observations_value_kind: Literal[ValueKind.OBSERVED] = ValueKind.OBSERVED
    calculations_value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    predicted: None = None
    predicted_value_kind: None = None
    analysis_price_rule: str
    detection_rule: str


class ProductSaleHistory(_FrozenModel):
    """Sale-event history for every variant of a product."""

    product_id: uuid.UUID
    events: tuple[SaleEventView, ...]
    variants: tuple[VariantSaleHistory, ...]
    provenance: SaleHistoryProvenance
    calculated_at: datetime
    predicted: None = None


class DetectedSaleWindow(_FrozenModel):
    """A calculated candidate sale window inferred from concurrent observed price drops.

    `value_kind` is always CALCULATED. This is not an observed retailer-published event.
    """

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    name: str
    retailer_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    start_date: datetime
    end_date: datetime
    event_type: SaleEventType
    source: Literal[SaleEventSource.OBSERVED_PRICE_INFERENCE] = (
        SaleEventSource.OBSERVED_PRICE_INFERENCE
    )
    source_ref: str = "calculated.observed_price_inference"
    confidence: ConfidenceLevel
    listing_count: int = Field(ge=0)
    median_drop_percent: Decimal | None = None
    observation_count: int = Field(ge=0)
