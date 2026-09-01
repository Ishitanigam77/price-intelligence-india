"""Retailer-agnostic expected-window and sale-opportunity records (Phase 19).

Projected dates and prices are estimates. They are never observed offers or guarantees.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    SaleEvidenceStatus,
    SaleMappingMethod,
    SaleSeverity,
)
from app.pricing.enums import MetricStatus, ValueKind
from app.pricing.money import quantize_money, quantize_ratio

TIMING_DISCLAIMER = (
    "Projected sale dates and prices are evidence-based estimates and are "
    "not guaranteed retailer announcements."
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ExpectedSaleWindow(_FrozenModel):
    """One family's current-year timing estimate (or UNKNOWN)."""

    sale_family: str
    display_name: str
    sale_type: SaleSeverity
    evidence_status: SaleEvidenceStatus
    mapping_method: SaleMappingMethod
    expected_start_date: datetime | None = None
    expected_end_date: datetime | None = None
    confidence: ConfidenceLevel
    evidence_count: int = Field(ge=0)
    historical_years_used: tuple[int, ...] = ()
    retailer_id: uuid.UUID | None = None
    occasion_id: str | None = None
    duration_days: int | None = Field(default=None, ge=0)
    as_of: datetime
    reason: str
    predicted: None = None


class ListingPredictionInput(_FrozenModel):
    """Optional Phase 10 prediction already labeled PREDICTED. Never invented here."""

    retailer_id: uuid.UUID
    seller_id: uuid.UUID | None = None
    status: str
    predicted_price: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class HistoricalSaleOccurrence(_FrozenModel):
    """Observed facts for one past window of a family, optionally retailer-scoped."""

    event_id: uuid.UUID
    sale_family: str
    retailer_id: uuid.UUID | None = None
    retailer_slug: str | None = None
    retailer_name: str | None = None
    start_date: datetime
    end_date: datetime
    duration_days: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    pre_sale_price: Decimal | None = None
    sale_price: Decimal | None = None
    minimum_sale_price: Decimal | None = None
    absolute_savings: Decimal | None = None
    percentage_savings: Decimal | None = None
    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus


class RetailerSaleOutlook(_FrozenModel):
    """Current vs expected-sale view for one retailer listing of an exact variant."""

    retailer_id: uuid.UUID
    retailer_slug: str
    retailer_name: str
    current_price: Decimal | None = None
    current_price_value_kind: ValueKind | None = None
    availability: AvailabilityStatus | None = None
    is_current_cheapest: bool = False
    expected_sale_price: Decimal | None = None
    expected_sale_price_value_kind: ValueKind | None = None
    predicted_sale_price: Decimal | None = None
    predicted_lower_bound: Decimal | None = None
    predicted_upper_bound: Decimal | None = None
    predicted_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    historical_sale_price: Decimal | None = None
    historical_occurrence_count: int = Field(ge=0)
    expected_saving: Decimal | None = None
    expected_saving_percentage: Decimal | None = None
    expected_saving_value_kind: Literal[ValueKind.CALCULATED] | None = None
    confidence: ConfidenceLevel | None = None
    reliability: ConfidenceLevel | None = None
    status: MetricStatus
    insufficient_reason: str | None = None


class SaleOpportunity(_FrozenModel):
    """Current vs one upcoming window (ordinary or major)."""

    sale_type: SaleSeverity
    window: ExpectedSaleWindow
    expected_price: Decimal | None = None
    expected_price_value_kind: ValueKind | None = None
    expected_saving: Decimal | None = None
    expected_saving_percentage: Decimal | None = None
    expected_saving_value_kind: Literal[ValueKind.CALCULATED] | None = None
    days_until_start: int | None = Field(default=None, ge=0)
    likely_best_retailer_id: uuid.UUID | None = None
    likely_best_retailer_slug: str | None = None
    likely_best_retailer_name: str | None = None
    retailer_outlooks: tuple[RetailerSaleOutlook, ...] = ()
    confidence: ConfidenceLevel | None = None
    historical_reliability: ConfidenceLevel | None = None
    status: MetricStatus
    insufficient_reason: str | None = None

    @field_validator("expected_saving", "expected_price")
    @classmethod
    def _quantize(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_money(value)

    @field_validator("expected_saving_percentage")
    @classmethod
    def _quantize_pct(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_ratio(value)


class VariantSaleIntelligence(_FrozenModel):
    """Phase 19 sale-timing intelligence for one exact product variant."""

    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    variant_key: str | None = None
    current_cheapest_retailer_id: uuid.UUID | None = None
    current_cheapest_retailer_slug: str | None = None
    current_cheapest_retailer_name: str | None = None
    current_cheapest_price: Decimal | None = None
    current_effective_price: Decimal | None = None
    current_availability: AvailabilityStatus | None = None
    occurrences: tuple[HistoricalSaleOccurrence, ...] = ()
    calendar: tuple[ExpectedSaleWindow, ...] = ()
    ordinary: SaleOpportunity | None = None
    major: SaleOpportunity | None = None
    expected_best_retailer: RetailerSaleOutlook | None = None
    disclaimer: str
    calculated_at: datetime
    predicted: None = None


class ProductSaleIntelligence(_FrozenModel):
    product_id: uuid.UUID
    as_of: datetime
    disclaimer: str
    variants: tuple[VariantSaleIntelligence, ...]
    predicted: None = None
