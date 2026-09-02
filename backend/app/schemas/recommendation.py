"""API schemas for `GET /api/v1/products/{product_id}/recommendation`.

The required decision payload (`recommendation`, `expected_saving`, `confidence`, `reasons`)
is returned per variant. Variants are never merged. Observed, calculated, and predicted
values stay labeled. A recommendation is never presented as a guarantee.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.pricing.enums import FreshnessStatus, TrendDirection, ValueKind
from app.recommendation.config import RECOMMENDATION_DISCLAIMER
from app.recommendation.enums import (
    BuyingWindow,
    InsufficientRecommendationReason,
    Recommendation,
    RuleId,
    Urgency,
)
from app.recommendation.models import OpportunitySnapshot, RecommendationResult


class RecommendationProvenanceRead(BaseModel):
    current_price_value_kind: ValueKind | None = None
    historical_value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    predicted_value_kind: Literal[ValueKind.PREDICTED] | None = None
    expected_saving_value_kind: Literal[ValueKind.CALCULATED] | None = None
    expected_saving_basis: str | None = None


class RecommendationEvidenceRead(BaseModel):
    current_effective_price: Decimal | None = None
    historical_percentile: Decimal | None = None
    historical_low: Decimal | None = None
    average_30d: Decimal | None = None
    average_90d: Decimal | None = None
    trend_direction: TrendDirection | None = None
    predicted_sale_price: Decimal | None = None
    prediction_confidence: float | None = None
    prediction_used: bool
    upcoming_sale_name: str | None = None
    upcoming_sale_days: int | None = None
    freshness_status: FreshnessStatus
    qualifying_observation_count: int
    expected_saving_basis: str | None = None
    urgency: Urgency | None = None
    buying_window: BuyingWindow | None = None
    ordinary_sale_name: str | None = None
    ordinary_sale_days: int | None = None
    major_sale_name: str | None = None
    major_sale_days: int | None = None


class OpportunitySnapshotRead(BaseModel):
    """Additive Phase 19 sale opportunity. Absent when evidence is insufficient."""

    model_config = ConfigDict(from_attributes=True)

    sale_type: str
    display_name: str | None = None
    evidence_status: str | None = None
    expected_start_date: datetime | None = None
    expected_end_date: datetime | None = None
    days_until_start: int | None = None
    expected_price: Decimal | None = None
    expected_price_value_kind: ValueKind | None = None
    expected_saving: Decimal | None = None
    expected_saving_percentage: Decimal | None = None
    expected_saving_value_kind: Literal[ValueKind.CALCULATED] | None = None
    likely_best_retailer_name: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    historical_reliability: str | None = None
    status: str | None = None


class VariantRecommendationRead(BaseModel):
    """One variant's BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA decision."""

    model_config = ConfigDict(from_attributes=True)

    product_variant_id: uuid.UUID
    recommendation: Recommendation
    expected_saving: Decimal | None = None
    expected_saving_percentage: Decimal | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reasons: list[str]
    triggered_rule_ids: list[RuleId]
    disclaimer: str = RECOMMENDATION_DISCLAIMER
    prediction_used: bool
    insufficient: InsufficientRecommendationReason | None = None
    provenance: RecommendationProvenanceRead
    evidence: RecommendationEvidenceRead
    buying_window: BuyingWindow | None = None
    urgency: Urgency | None = None
    ordinary_opportunity: OpportunitySnapshotRead | None = None
    major_opportunity: OpportunitySnapshotRead | None = None


class ProductRecommendationRead(BaseModel):
    """Recommendations for every requested variant of a product. Variants are never mixed."""

    product_id: uuid.UUID
    as_of: datetime
    disclaimer: str = RECOMMENDATION_DISCLAIMER
    phase10_status: str | None = None
    phase10_model_version: str | None = None
    variants: list[VariantRecommendationRead]


def _opportunity_read(snapshot: OpportunitySnapshot | None) -> OpportunitySnapshotRead | None:
    if snapshot is None:
        return None
    return OpportunitySnapshotRead.model_validate(snapshot)


def variant_recommendation_read(result: RecommendationResult) -> VariantRecommendationRead:
    predicted_kind = ValueKind.PREDICTED if result.prediction_used else None
    return VariantRecommendationRead(
        product_variant_id=result.product_variant_id,
        recommendation=result.recommendation,
        expected_saving=result.expected_saving,
        expected_saving_percentage=result.expected_saving_percentage,
        confidence=result.confidence,
        reasons=list(result.reasons),
        triggered_rule_ids=list(result.triggered_rule_ids),
        disclaimer=result.disclaimer,
        prediction_used=result.prediction_used,
        insufficient=result.insufficient,
        provenance=RecommendationProvenanceRead(
            current_price_value_kind=result.evidence.current_price_value_kind,
            predicted_value_kind=predicted_kind,
            expected_saving_value_kind=result.expected_saving_value_kind,
            expected_saving_basis=result.evidence.expected_saving_basis,
        ),
        evidence=RecommendationEvidenceRead(
            current_effective_price=result.evidence.current_effective_price,
            historical_percentile=result.evidence.historical_percentile,
            historical_low=result.evidence.historical_low,
            average_30d=result.evidence.average_30d,
            average_90d=result.evidence.average_90d,
            trend_direction=result.evidence.trend_direction,
            predicted_sale_price=result.evidence.predicted_sale_price,
            prediction_confidence=result.evidence.prediction_confidence,
            prediction_used=result.evidence.prediction_used,
            upcoming_sale_name=result.evidence.upcoming_sale_name,
            upcoming_sale_days=result.evidence.upcoming_sale_days,
            freshness_status=result.evidence.freshness_status,
            qualifying_observation_count=result.evidence.qualifying_observation_count,
            expected_saving_basis=result.evidence.expected_saving_basis,
            urgency=result.evidence.urgency,
            buying_window=result.evidence.buying_window,
            ordinary_sale_name=result.evidence.ordinary_sale_name,
            ordinary_sale_days=result.evidence.ordinary_sale_days,
            major_sale_name=result.evidence.major_sale_name,
            major_sale_days=result.evidence.major_sale_days,
        ),
        buying_window=result.buying_window,
        urgency=result.urgency,
        ordinary_opportunity=_opportunity_read(result.ordinary_opportunity),
        major_opportunity=_opportunity_read(result.major_opportunity),
    )


def product_recommendation_read(
    *,
    product_id: uuid.UUID,
    as_of: datetime,
    phase10_status: str | None,
    phase10_model_version: str | None,
    results: list[RecommendationResult],
) -> ProductRecommendationRead:
    return ProductRecommendationRead(
        product_id=product_id,
        as_of=as_of,
        disclaimer=RECOMMENDATION_DISCLAIMER,
        phase10_status=phase10_status,
        phase10_model_version=phase10_model_version,
        variants=[variant_recommendation_read(item) for item in results],
    )
