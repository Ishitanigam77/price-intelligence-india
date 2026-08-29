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
from app.recommendation.enums import InsufficientRecommendationReason, Recommendation, RuleId
from app.recommendation.models import RecommendationResult


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


class VariantRecommendationRead(BaseModel):
    """One variant's BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA decision."""

    model_config = ConfigDict(from_attributes=True)

    product_variant_id: uuid.UUID
    recommendation: Recommendation
    expected_saving: Decimal | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reasons: list[str]
    triggered_rule_ids: list[RuleId]
    disclaimer: str = RECOMMENDATION_DISCLAIMER
    prediction_used: bool
    insufficient: InsufficientRecommendationReason | None = None
    provenance: RecommendationProvenanceRead
    evidence: RecommendationEvidenceRead


class ProductRecommendationRead(BaseModel):
    """Recommendations for every requested variant of a product. Variants are never mixed."""

    product_id: uuid.UUID
    as_of: datetime
    disclaimer: str = RECOMMENDATION_DISCLAIMER
    phase10_status: str | None = None
    phase10_model_version: str | None = None
    variants: list[VariantRecommendationRead]


def variant_recommendation_read(result: RecommendationResult) -> VariantRecommendationRead:
    predicted_kind = ValueKind.PREDICTED if result.prediction_used else None
    return VariantRecommendationRead(
        product_variant_id=result.product_variant_id,
        recommendation=result.recommendation,
        expected_saving=result.expected_saving,
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
        ),
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
