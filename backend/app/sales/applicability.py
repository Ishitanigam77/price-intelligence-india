"""Which sale events apply to a product or to a single price observation.

Applicability is generic: optional retailer / category / brand identifiers on the event are
compared to the product (and observation retailer). No retailer identity is hardcoded.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.pricing.history_models import HistoricalObservationPoint
from app.sales.models import SaleEventRecord, SalePricePoint


def event_applies_to_product(
    event: SaleEventRecord,
    *,
    brand_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    retailer_id: uuid.UUID | None = None,
) -> bool:
    """Whether `event` can apply to a product with the given brand/category.

    A null scope on the event means "not constrained on that dimension". When `retailer_id`
    is provided, retailer-specific events for a *different* retailer are excluded.
    """
    if event.brand_id is not None and event.brand_id != brand_id:
        return False
    if event.category_id is not None and event.category_id != category_id:
        return False
    event_retailer = event.retailer_id
    if retailer_id is not None and event_retailer is not None and event_retailer != retailer_id:
        return False
    return True


def observation_belongs_to_event(
    event: SaleEventRecord,
    point: HistoricalObservationPoint,
    *,
    brand_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
) -> bool:
    """Whether a stored observation falls inside `event`'s window and scope."""
    if not event_applies_to_product(
        event,
        brand_id=brand_id,
        category_id=category_id,
        retailer_id=point.retailer_id,
    ):
        return False
    return event.start_date <= point.observed_at <= event.end_date


def applicable_events(
    events: Sequence[SaleEventRecord],
    *,
    brand_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    retailer_id: uuid.UUID | None = None,
) -> tuple[SaleEventRecord, ...]:
    return tuple(
        event
        for event in events
        if event_applies_to_product(
            event, brand_id=brand_id, category_id=category_id, retailer_id=retailer_id
        )
    )


def observations_during_event(
    event: SaleEventRecord,
    points: Sequence[SalePricePoint],
) -> tuple[HistoricalObservationPoint, ...]:
    matching: list[HistoricalObservationPoint] = []
    for point in points:
        if observation_belongs_to_event(
            event,
            point.observation,
            brand_id=point.brand_id,
            category_id=point.category_id,
        ):
            matching.append(point.observation)
    matching.sort(key=lambda item: (item.observed_at, item.created_at, item.snapshot_id))
    return tuple(matching)
