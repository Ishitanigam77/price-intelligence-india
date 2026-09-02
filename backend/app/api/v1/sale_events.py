"""Sale-event API routes.

`GET /sale-events` lists persisted sale windows. `GET /sale-events/upcoming` is the
before-event subset ordered by start_date. Lifecycle status is derived from dates, never
stored. This module does not invent real-world campaigns or predict prices.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SaleEventServiceDep, SaleIntelligenceServiceDep
from app.domain.enums import SaleEventSource, SaleEventStatus, SaleEventType
from app.schemas.common import Page
from app.schemas.intelligence import SaleCalendarPage
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.sale_event import SaleEventRead

router = APIRouter(prefix="/sale-events", tags=["sale-events"])


@router.get("", response_model=Page[SaleEventRead])
def list_sale_events(
    service: SaleEventServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    event_type: SaleEventType | None = None,
    source: SaleEventSource | None = None,
    retailer_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    status: SaleEventStatus | None = None,
) -> Page[SaleEventRead]:
    """List persisted sale events. Optional filters never invent missing rows."""
    return service.list_events(
        event_type=event_type,
        source=source,
        retailer_id=retailer_id,
        category_id=category_id,
        brand_id=brand_id,
        status=status,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/upcoming", response_model=Page[SaleEventRead])
def list_upcoming_sale_events(
    service: SaleEventServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    retailer_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
) -> Page[SaleEventRead]:
    """Sale events whose `start_date` is still in the future (status `before_event`)."""
    return service.list_upcoming(
        retailer_id=retailer_id,
        category_id=category_id,
        brand_id=brand_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/calendar", response_model=SaleCalendarPage)
def list_sale_calendar(
    service: SaleIntelligenceServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    as_of: Annotated[
        datetime | None,
        Query(description="Optional analysis instant. Defaults to now."),
    ] = None,
) -> SaleCalendarPage:
    """Expected current-year sale windows mapped from historical events.

    Projected dates are evidence-based estimates and are not guaranteed retailer
    announcements. CONFIRMED is used only when a persisted permitted/curated future
    event exists.
    """
    return service.list_calendar(
        as_of=as_of,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{event_id}", response_model=SaleEventRead)
def get_sale_event(event_id: uuid.UUID, service: SaleEventServiceDep) -> SaleEventRead:
    return service.get_event(event_id)
