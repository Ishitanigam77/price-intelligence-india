"""API schemas for sale events and product sale history.

Observed in-window prices, calculated sale statistics, and (absent) predictions are kept as
separate fields. A missing calculation is `insufficient_history` with an explicit reason —
never a fabricated zero or synthetic event.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    SaleEventSource,
    SaleEventStatus,
    SaleEventType,
    SourceType,
)
from app.pricing.enums import MetricStatus, ValueKind
from app.pricing.history_models import HistoricalObservationPoint
from app.sales.enums import SaleInsufficientReasonCode
from app.sales.models import (
    EventWindowHistory,
    ProductSaleHistory,
    SaleCalculatedMetric,
    SaleEventView,
    VariantSaleHistory,
)
from app.schemas.common import Page


class SaleEventRead(BaseModel):
    """Public representation of a sale event, including derived lifecycle status."""

    model_config = ConfigDict(from_attributes=True)

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
    status: SaleEventStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SaleInsufficientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: SaleInsufficientReasonCode
    reason: str


class SaleCalculatedMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    status: MetricStatus
    value: Decimal | None = None
    unit: str
    observation_count: int
    calculated_at: datetime
    insufficient: SaleInsufficientRead | None = None
    extra: dict[str, Decimal | int | str | None] = Field(default_factory=dict)


class SaleHistoryObservationRead(BaseModel):
    """One stored price observation that fell inside a sale window. Always OBSERVED."""

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


class EventWindowHistoryRead(BaseModel):
    event: SaleEventRead
    observations: Page[SaleHistoryObservationRead]
    observation_count: int
    sale_average: SaleCalculatedMetricRead
    sale_low: SaleCalculatedMetricRead
    sale_high: SaleCalculatedMetricRead
    vs_non_sale_baseline_percent: SaleCalculatedMetricRead


class VariantSaleHistoryRead(BaseModel):
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    variant_key: str | None = None
    event_windows: list[EventWindowHistoryRead]
    qualifying_observation_count: int
    excluded_unverified_observation_count: int
    overall_sale_average: SaleCalculatedMetricRead
    overall_sale_low: SaleCalculatedMetricRead
    overall_sale_high: SaleCalculatedMetricRead
    non_sale_baseline: SaleCalculatedMetricRead
    vs_non_sale_baseline_percent: SaleCalculatedMetricRead
    calculated_at: datetime


class SaleHistoryProvenanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observations_value_kind: Literal[ValueKind.OBSERVED] = ValueKind.OBSERVED
    calculations_value_kind: Literal[ValueKind.CALCULATED] = ValueKind.CALCULATED
    predicted: None = None
    predicted_value_kind: None = None
    analysis_price_rule: str
    detection_rule: str


class ProductSaleHistoryRead(BaseModel):
    """Response for `GET /api/v1/products/{product_id}/sale-history`."""

    product_id: uuid.UUID
    events: list[SaleEventRead]
    variants: list[VariantSaleHistoryRead]
    provenance: SaleHistoryProvenanceRead
    calculated_at: datetime
    predicted: None = None


def sale_event_read(
    view: SaleEventView,
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> SaleEventRead:
    event = view.event
    return SaleEventRead(
        id=event.id,
        name=event.name,
        retailer_id=event.retailer_id,
        category_id=event.category_id,
        brand_id=event.brand_id,
        start_date=event.start_date,
        end_date=event.end_date,
        event_type=event.event_type,
        source=event.source,
        source_ref=event.source_ref,
        confidence=event.confidence,
        status=view.status,
        created_at=created_at,
        updated_at=updated_at,
    )


def _metric_read(metric: SaleCalculatedMetric) -> SaleCalculatedMetricRead:
    return SaleCalculatedMetricRead.model_validate(metric)


def _observation_read(point: HistoricalObservationPoint) -> SaleHistoryObservationRead:
    return SaleHistoryObservationRead(
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


def _paginate_observations(
    observations: tuple[HistoricalObservationPoint, ...],
    *,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> Page[HistoricalObservationPoint]:
    filtered = [
        point
        for point in observations
        if (since is None or point.observed_at >= since)
        and (until is None or point.observed_at <= until)
    ]
    window = filtered[offset : offset + limit]
    return Page[HistoricalObservationPoint](
        items=window, total=len(filtered), limit=limit, offset=offset
    )


def _event_window_read(
    window: EventWindowHistory,
    *,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> EventWindowHistoryRead:
    page = _paginate_observations(
        window.observations, since=since, until=until, limit=limit, offset=offset
    )
    return EventWindowHistoryRead(
        event=sale_event_read(window.event),
        observations=Page[SaleHistoryObservationRead](
            items=[_observation_read(item) for item in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        ),
        observation_count=window.observation_count,
        sale_average=_metric_read(window.sale_average),
        sale_low=_metric_read(window.sale_low),
        sale_high=_metric_read(window.sale_high),
        vs_non_sale_baseline_percent=_metric_read(window.vs_non_sale_baseline_percent),
    )


def _variant_read(
    variant: VariantSaleHistory,
    *,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> VariantSaleHistoryRead:
    return VariantSaleHistoryRead(
        product_id=variant.product_id,
        product_variant_id=variant.product_variant_id,
        variant_key=variant.variant_key,
        event_windows=[
            _event_window_read(window, since=since, until=until, limit=limit, offset=offset)
            for window in variant.event_windows
        ],
        qualifying_observation_count=variant.qualifying_observation_count,
        excluded_unverified_observation_count=variant.excluded_unverified_observation_count,
        overall_sale_average=_metric_read(variant.overall_sale_average),
        overall_sale_low=_metric_read(variant.overall_sale_low),
        overall_sale_high=_metric_read(variant.overall_sale_high),
        non_sale_baseline=_metric_read(variant.non_sale_baseline),
        vs_non_sale_baseline_percent=_metric_read(variant.vs_non_sale_baseline_percent),
        calculated_at=variant.calculated_at,
    )


def product_sale_history_read(
    history: ProductSaleHistory,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ProductSaleHistoryRead:
    return ProductSaleHistoryRead(
        product_id=history.product_id,
        events=[sale_event_read(event) for event in history.events],
        variants=[
            _variant_read(variant, since=since, until=until, limit=limit, offset=offset)
            for variant in history.variants
        ],
        provenance=SaleHistoryProvenanceRead.model_validate(history.provenance),
        calculated_at=history.calculated_at,
        predicted=None,
    )
