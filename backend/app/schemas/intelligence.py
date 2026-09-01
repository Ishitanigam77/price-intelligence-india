"""API schemas for Phase 19 sale-timing intelligence.

Projected dates and prices are labeled as confirmed / expected / inferred / unknown.
They are never presented as guaranteed retailer announcements.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    SaleEvidenceStatus,
    SaleMappingMethod,
    SaleSeverity,
)
from app.pricing.enums import MetricStatus, ValueKind
from app.sales.timing_models import (
    TIMING_DISCLAIMER,
    ExpectedSaleWindow,
    HistoricalSaleOccurrence,
    ProductSaleIntelligence,
    RetailerSaleOutlook,
    SaleOpportunity,
    VariantSaleIntelligence,
)


class ExpectedSaleWindowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sale_family: str
    display_name: str
    sale_type: SaleSeverity
    evidence_status: SaleEvidenceStatus
    mapping_method: SaleMappingMethod
    expected_start_date: datetime | None = None
    expected_end_date: datetime | None = None
    confidence: ConfidenceLevel
    evidence_count: int
    historical_years_used: list[int]
    retailer_id: uuid.UUID | None = None
    occasion_id: str | None = None
    duration_days: int | None = None
    reason: str
    predicted: None = None


class HistoricalSaleOccurrenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    sale_family: str
    retailer_id: uuid.UUID | None = None
    retailer_slug: str | None = None
    retailer_name: str | None = None
    start_date: datetime
    end_date: datetime
    duration_days: int
    observation_count: int
    pre_sale_price: Decimal | None = None
    sale_price: Decimal | None = None
    minimum_sale_price: Decimal | None = None
    absolute_savings: Decimal | None = None
    percentage_savings: Decimal | None = None
    value_kind: ValueKind
    status: MetricStatus


class RetailerSaleOutlookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    retailer_id: uuid.UUID
    retailer_slug: str
    retailer_name: str
    current_price: Decimal | None = None
    current_price_value_kind: ValueKind | None = None
    availability: AvailabilityStatus | None = None
    is_current_cheapest: bool
    expected_sale_price: Decimal | None = None
    expected_sale_price_value_kind: ValueKind | None = None
    predicted_sale_price: Decimal | None = None
    predicted_lower_bound: Decimal | None = None
    predicted_upper_bound: Decimal | None = None
    predicted_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    historical_sale_price: Decimal | None = None
    historical_occurrence_count: int
    expected_saving: Decimal | None = None
    expected_saving_percentage: Decimal | None = None
    expected_saving_value_kind: ValueKind | None = None
    confidence: ConfidenceLevel | None = None
    reliability: ConfidenceLevel | None = None
    status: MetricStatus
    insufficient_reason: str | None = None


class SaleOpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sale_type: SaleSeverity
    window: ExpectedSaleWindowRead
    expected_price: Decimal | None = None
    expected_price_value_kind: ValueKind | None = None
    expected_saving: Decimal | None = None
    expected_saving_percentage: Decimal | None = None
    expected_saving_value_kind: ValueKind | None = None
    days_until_start: int | None = None
    likely_best_retailer_id: uuid.UUID | None = None
    likely_best_retailer_slug: str | None = None
    likely_best_retailer_name: str | None = None
    retailer_outlooks: list[RetailerSaleOutlookRead]
    confidence: ConfidenceLevel | None = None
    historical_reliability: ConfidenceLevel | None = None
    status: MetricStatus
    insufficient_reason: str | None = None


class VariantSaleIntelligenceRead(BaseModel):
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    variant_key: str | None = None
    current_cheapest_retailer_id: uuid.UUID | None = None
    current_cheapest_retailer_slug: str | None = None
    current_cheapest_retailer_name: str | None = None
    current_cheapest_price: Decimal | None = None
    current_effective_price: Decimal | None = None
    current_availability: AvailabilityStatus | None = None
    occurrences: list[HistoricalSaleOccurrenceRead]
    calendar: list[ExpectedSaleWindowRead]
    ordinary: SaleOpportunityRead | None = None
    major: SaleOpportunityRead | None = None
    expected_best_retailer: RetailerSaleOutlookRead | None = None
    disclaimer: str = TIMING_DISCLAIMER
    calculated_at: datetime
    predicted: None = None


class ProductSaleIntelligenceRead(BaseModel):
    product_id: uuid.UUID
    as_of: datetime
    disclaimer: str = TIMING_DISCLAIMER
    variants: list[VariantSaleIntelligenceRead]
    predicted: None = None


class SaleCalendarPage(BaseModel):
    as_of: datetime
    disclaimer: str = TIMING_DISCLAIMER
    items: list[ExpectedSaleWindowRead]
    total: int
    limit: int
    offset: int


def expected_window_read(window: ExpectedSaleWindow) -> ExpectedSaleWindowRead:
    return ExpectedSaleWindowRead(
        sale_family=window.sale_family,
        display_name=window.display_name,
        sale_type=window.sale_type,
        evidence_status=window.evidence_status,
        mapping_method=window.mapping_method,
        expected_start_date=window.expected_start_date,
        expected_end_date=window.expected_end_date,
        confidence=window.confidence,
        evidence_count=window.evidence_count,
        historical_years_used=list(window.historical_years_used),
        retailer_id=window.retailer_id,
        occasion_id=window.occasion_id,
        duration_days=window.duration_days,
        reason=window.reason,
        predicted=None,
    )


def _occurrence_read(item: HistoricalSaleOccurrence) -> HistoricalSaleOccurrenceRead:
    return HistoricalSaleOccurrenceRead.model_validate(item)


def _outlook_read(item: RetailerSaleOutlook) -> RetailerSaleOutlookRead:
    return RetailerSaleOutlookRead.model_validate(item)


def _opportunity_read(item: SaleOpportunity | None) -> SaleOpportunityRead | None:
    if item is None:
        return None
    return SaleOpportunityRead(
        sale_type=item.sale_type,
        window=expected_window_read(item.window),
        expected_price=item.expected_price,
        expected_price_value_kind=item.expected_price_value_kind,
        expected_saving=item.expected_saving,
        expected_saving_percentage=item.expected_saving_percentage,
        expected_saving_value_kind=item.expected_saving_value_kind,
        days_until_start=item.days_until_start,
        likely_best_retailer_id=item.likely_best_retailer_id,
        likely_best_retailer_slug=item.likely_best_retailer_slug,
        likely_best_retailer_name=item.likely_best_retailer_name,
        retailer_outlooks=[_outlook_read(row) for row in item.retailer_outlooks],
        confidence=item.confidence,
        historical_reliability=item.historical_reliability,
        status=item.status,
        insufficient_reason=item.insufficient_reason,
    )


def _variant_read(variant: VariantSaleIntelligence) -> VariantSaleIntelligenceRead:
    return VariantSaleIntelligenceRead(
        product_id=variant.product_id,
        product_variant_id=variant.product_variant_id,
        variant_key=variant.variant_key,
        current_cheapest_retailer_id=variant.current_cheapest_retailer_id,
        current_cheapest_retailer_slug=variant.current_cheapest_retailer_slug,
        current_cheapest_retailer_name=variant.current_cheapest_retailer_name,
        current_cheapest_price=variant.current_cheapest_price,
        current_effective_price=variant.current_effective_price,
        current_availability=variant.current_availability,
        occurrences=[_occurrence_read(item) for item in variant.occurrences],
        calendar=[expected_window_read(item) for item in variant.calendar],
        ordinary=_opportunity_read(variant.ordinary),
        major=_opportunity_read(variant.major),
        expected_best_retailer=(
            _outlook_read(variant.expected_best_retailer)
            if variant.expected_best_retailer is not None
            else None
        ),
        disclaimer=variant.disclaimer,
        calculated_at=variant.calculated_at,
        predicted=None,
    )


def product_sale_intelligence_read(
    payload: ProductSaleIntelligence,
) -> ProductSaleIntelligenceRead:
    return ProductSaleIntelligenceRead(
        product_id=payload.product_id,
        as_of=payload.as_of,
        disclaimer=payload.disclaimer,
        variants=[_variant_read(item) for item in payload.variants],
        predicted=None,
    )
