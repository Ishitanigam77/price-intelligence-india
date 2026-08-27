"""Retailer-agnostic inputs and outputs of historical price intelligence.

The engine never sees ORM objects or HTTP schemas. Callers project stored `PriceSnapshot`
rows into `HistoricalObservationPoint` values. Every aggregate is labeled CALCULATED and is
withheld (never zero-filled) when history is insufficient. Predicted values are not produced.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.domain.validation import validate_currency_code, validate_required_non_negative_amount
from app.pricing.enums import (
    InsufficientReasonCode,
    MetricStatus,
    TrendDirection,
    ValueKind,
)
from app.pricing.models import DataFreshness
from app.pricing.money import quantize_money

VERIFIED_CONFIDENCE_LEVELS = frozenset({ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM})

PRICE_DROP_BASELINE_DESCRIPTION = (
    "Immediately previous qualifying verified observation for the same product variant, "
    "retailer listing (retailer_product_id), and seller_id (including the no-seller case). "
    "Observations from other sellers or retailers are never used as this listing's baseline."
)

ANALYSIS_PRICE_RULE = (
    "Each qualifying observation contributes its stored effective_price when that field was "
    "recorded, otherwise its observed displayed_price. Missing prices are never invented."
)

TREND_METHOD_DESCRIPTION = (
    "Ordinary least squares slope of analysis price against observation time, using all "
    "qualifying verified observations of this exact product variant. Classified as stable "
    "when the implied percent change over the observed span is within "
    "PRICING_TREND_STABLE_PERCENT. This is a historical description, not a forecast."
)

AVERAGE_WINDOW_DAYS: tuple[int, ...] = (7, 30, 90, 180)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class HistoricalObservationPoint(_FrozenModel):
    """One stored price observation as the historical engine sees it."""

    snapshot_id: uuid.UUID
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    variant_key: str | None = None
    retailer_id: uuid.UUID
    retailer_slug: str
    retailer_name: str
    retailer_product_id: uuid.UUID
    seller_id: uuid.UUID | None = None
    source_url: str | None = None
    source_type: SourceType
    observed_at: datetime
    created_at: datetime
    currency: str = "INR"
    displayed_price: Decimal
    effective_price: Decimal | None = None
    mrp: Decimal | None = None
    availability: AvailabilityStatus
    confidence: ConfidenceLevel

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)

    @field_validator("observed_at", "created_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Observation timestamps must be timezone-aware.")
        return value

    @field_validator("displayed_price")
    @classmethod
    def _validate_displayed(cls, value: Decimal) -> Decimal:
        validated = validate_required_non_negative_amount(value, field_name="displayed_price")
        return quantize_money(validated)

    @field_validator("effective_price", "mrp")
    @classmethod
    def _validate_optional_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_money(validate_required_non_negative_amount(value, field_name="amount"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_kind(self) -> Literal[ValueKind.OBSERVED]:
        return ValueKind.OBSERVED

    @computed_field  # type: ignore[prop-decorator]
    @property
    def analysis_price(self) -> Decimal:
        """Price used for historical calculations. Never invented."""
        return self.effective_price if self.effective_price is not None else self.displayed_price

    @computed_field  # type: ignore[prop-decorator]
    @property
    def analysis_price_field(self) -> Literal["effective_price", "displayed_price"]:
        return "effective_price" if self.effective_price is not None else "displayed_price"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def qualifies_for_calculations(self) -> bool:
        return self.confidence in VERIFIED_CONFIDENCE_LEVELS

    @property
    def listing_key(self) -> tuple[uuid.UUID, uuid.UUID | None]:
        """Seller-aware listing identity; None seller is distinct from any named seller."""
        return (self.retailer_product_id, self.seller_id)


class InsufficientHistory(_FrozenModel):
    code: InsufficientReasonCode
    reason: str


class CalculatedMetric(_FrozenModel):
    """A derived historical statistic. `value` is None when history is insufficient."""

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus
    value: Decimal | None = None
    unit: str
    window_days: int | None = None
    observation_count: int = Field(ge=0)
    calculated_at: datetime
    insufficient: InsufficientHistory | None = None
    extra: dict[str, Decimal | int | str | None] = Field(default_factory=dict)


class ExtremaMetric(CalculatedMetric):
    """Historical min or max, with the observation that produced it when available."""

    snapshot_id: uuid.UUID | None = None
    observed_at: datetime | None = None
    retailer_id: uuid.UUID | None = None
    seller_id: uuid.UUID | None = None
    source_url: str | None = None


class PriceDropResult(_FrozenModel):
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
    baseline_description: str = PRICE_DROP_BASELINE_DESCRIPTION
    observation_count: int = Field(ge=0)
    calculated_at: datetime
    insufficient: InsufficientHistory | None = None


class TrendResult(_FrozenModel):
    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus
    direction: TrendDirection
    implied_percent_change: Decimal | None = None
    slope_per_day: Decimal | None = None
    method: str = TREND_METHOD_DESCRIPTION
    observation_count: int = Field(ge=0)
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    calculated_at: datetime
    insufficient: InsufficientHistory | None = None


class HistoryProvenance(_FrozenModel):
    observations_value_kind: Literal[ValueKind.OBSERVED] = ValueKind.OBSERVED
    calculations_value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    predicted: None = None
    predicted_value_kind: None = None
    analysis_price_rule: str = ANALYSIS_PRICE_RULE
    price_drop_baseline: str = PRICE_DROP_BASELINE_DESCRIPTION
    trend_method: str = TREND_METHOD_DESCRIPTION


class VariantHistory(_FrozenModel):
    """Historical intelligence for a single matched product variant."""

    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    variant_key: str | None = None
    observations: tuple[HistoricalObservationPoint, ...]
    qualifying_observation_count: int
    excluded_unverified_observation_count: int
    current_observation: HistoricalObservationPoint | None
    average_7d: CalculatedMetric
    average_30d: CalculatedMetric
    average_90d: CalculatedMetric
    average_180d: CalculatedMetric
    historical_low: ExtremaMetric
    historical_high: ExtremaMetric
    current_price_percentile: CalculatedMetric
    volatility: CalculatedMetric
    percentage_change: CalculatedMetric
    price_drop: PriceDropResult
    trend: TrendResult
    data_freshness: DataFreshness
    provenance: HistoryProvenance
    calculated_at: datetime


class ProductHistory(_FrozenModel):
    """Historical intelligence for every variant of a product. Variants are never mixed."""

    product_id: uuid.UUID
    variants: tuple[VariantHistory, ...]
    data_freshness: DataFreshness
    provenance: HistoryProvenance
    calculated_at: datetime
    predicted: None = None
