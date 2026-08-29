"""Retailer-agnostic inputs and outputs of the recommendation engine.

The engine never sees ORM objects or HTTP schemas. Callers project Phase 7 history, Phase 9
sale-event views, and Phase 10 prediction outputs into these records. Observed, calculated,
and predicted values stay labeled separately (`PROJECT_ARCHITECTURE.md` §6). Missing inputs
are explicit `None` — never zero-filled or invented.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import ConfidenceLevel, SaleEventSource, SaleEventStatus
from app.pricing.enums import FreshnessStatus, MetricStatus, TrendDirection, ValueKind
from app.pricing.money import quantize_money
from app.recommendation.config import RECOMMENDATION_DISCLAIMER
from app.recommendation.enums import InsufficientRecommendationReason, Recommendation, RuleId


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class OptionalMetric(_FrozenModel):
    """A numeric input with provenance. `value` is None when that input is unavailable."""

    value: Decimal | None = None
    value_kind: ValueKind
    status: MetricStatus
    unit: str
    observation_count: int | None = Field(default=None, ge=0)
    window_days: int | None = None

    @field_validator("value")
    @classmethod
    def _quantize_optional_money_or_ratio(cls, value: Decimal | None) -> Decimal | None:
        return value


class PredictionInput(_FrozenModel):
    """Phase 10 prediction as the recommendation engine sees it.

    `predicted_price` is always `value_kind=PREDICTED`. A missing or low-confidence
    prediction is not replaced with a fabricated price.
    """

    value_kind: Literal[ValueKind.PREDICTED] = ValueKind.PREDICTED
    is_prediction: Literal[True] = True
    status: str
    predicted_price: Decimal | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    insufficient_reason: str | None = None
    product_variant_id: uuid.UUID | None = None
    retailer_id: uuid.UUID | None = None
    seller_id: uuid.UUID | None = None
    model_version: str | None = None

    @field_validator("predicted_price")
    @classmethod
    def _quantize_predicted(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_money(value)


class UpcomingSaleInput(_FrozenModel):
    """One upcoming sale window. Dates and confidence come from Phase 9, never invented."""

    event_id: uuid.UUID
    name: str
    start_date: datetime
    end_date: datetime
    confidence: ConfidenceLevel
    source: SaleEventSource
    status: SaleEventStatus
    days_until_start: int = Field(ge=0)

    @field_validator("start_date", "end_date")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Sale event dates must be timezone-aware.")
        return value


class RecommendationInput(_FrozenModel):
    """All signals available for one product variant at `as_of`. Variants are never mixed."""

    as_of: datetime
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    currency: str = "INR"
    current_effective_price: Decimal | None = None
    current_price_value_kind: ValueKind | None = None
    current_price_field: str | None = None
    qualifying_observation_count: int = Field(ge=0)
    freshness_status: FreshnessStatus
    historical_percentile: OptionalMetric | None = None
    historical_low: OptionalMetric | None = None
    average_30d: OptionalMetric | None = None
    average_90d: OptionalMetric | None = None
    trend_direction: TrendDirection | None = None
    prediction: PredictionInput | None = None
    upcoming_events: tuple[UpcomingSaleInput, ...] = ()

    @field_validator("as_of")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Recommendation timestamps must be timezone-aware.")
        return value

    @field_validator("current_effective_price")
    @classmethod
    def _quantize_current(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_money(value)


class EvaluatedRule(_FrozenModel):
    """One explicit rule after evaluation against the actual inputs."""

    rule_id: RuleId
    fired: bool
    reason: str
    supports: Recommendation | None = None


class EvidenceSnapshot(_FrozenModel):
    """The values actually consumed. Absent inputs stay None — never filled in."""

    current_effective_price: Decimal | None = None
    current_price_value_kind: ValueKind | None = None
    historical_percentile: Decimal | None = None
    historical_low: Decimal | None = None
    average_30d: Decimal | None = None
    average_90d: Decimal | None = None
    trend_direction: TrendDirection | None = None
    predicted_sale_price: Decimal | None = None
    prediction_confidence: float | None = None
    prediction_used: bool = False
    upcoming_sale_name: str | None = None
    upcoming_sale_days: int | None = None
    freshness_status: FreshnessStatus
    qualifying_observation_count: int = Field(ge=0)
    expected_saving_basis: str | None = None


class RecommendationResult(_FrozenModel):
    """Deterministic recommendation for one variant. Not a guaranteed outcome."""

    recommendation: Recommendation
    expected_saving: Decimal | None = None
    expected_saving_value_kind: Literal[ValueKind.CALCULATED] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reasons: tuple[str, ...]
    triggered_rule_ids: tuple[RuleId, ...]
    disclaimer: str = RECOMMENDATION_DISCLAIMER
    prediction_used: bool = False
    insufficient: InsufficientRecommendationReason | None = None
    evidence: EvidenceSnapshot
    evaluated_rules: tuple[EvaluatedRule, ...] = ()
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    as_of: datetime
    currency: str = "INR"

    @field_validator("expected_saving")
    @classmethod
    def _quantize_saving(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_money(value)
