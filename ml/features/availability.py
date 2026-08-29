"""Cutoff helpers so features only use information available at prediction time."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.domain.enums import SaleEventSource
from app.pricing.history import qualifying_observations
from app.pricing.history_models import HistoricalObservationPoint
from app.sales.models import SaleEventRecord, SalePricePoint

SOURCES_KNOWN_IN_ADVANCE = frozenset(
    {
        SaleEventSource.MANUAL_CURATION,
        SaleEventSource.OFFICIAL_API,
        SaleEventSource.AFFILIATE_FEED,
        SaleEventSource.PRODUCT_FEED,
        SaleEventSource.OTHER_PERMITTED,
    }
)


def observation_available_at(point: HistoricalObservationPoint, *, as_of: datetime) -> bool:
    """An observation is usable at T only if it was observed and recorded strictly before T."""
    return point.observed_at < as_of and point.created_at < as_of


def observations_available_at(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
) -> tuple[HistoricalObservationPoint, ...]:
    """Qualifying verified observations known strictly before `as_of`. Never future rows."""
    return tuple(
        point
        for point in qualifying_observations(points)
        if observation_available_at(point, as_of=as_of)
    )


def sale_points_available_at(
    points: Sequence[SalePricePoint],
    *,
    as_of: datetime,
) -> tuple[SalePricePoint, ...]:
    return tuple(
        point
        for point in points
        if point.observation.qualifies_for_calculations
        and observation_available_at(point.observation, as_of=as_of)
    )


def event_schedule_known_at(event: SaleEventRecord, *, as_of: datetime) -> bool:
    """Whether the event's identity/schedule would have been known at `as_of`.

    Curated and permitted-source events are treated as published schedules. Inferred events
    are calculated from observed drops, so they are only historical facts after they end.
    """
    if event.source is SaleEventSource.OBSERVED_PRICE_INFERENCE:
        return event.end_date < as_of
    return event.source in SOURCES_KNOWN_IN_ADVANCE


def completed_events_before(
    events: Sequence[SaleEventRecord],
    *,
    as_of: datetime,
) -> tuple[SaleEventRecord, ...]:
    """Sale windows that had already ended by T — usable as previous-sale history."""
    return tuple(event for event in events if event.end_date < as_of)


def known_active_or_upcoming_event(
    events: Sequence[SaleEventRecord],
    *,
    as_of: datetime,
    target_event: SaleEventRecord | None = None,
) -> SaleEventRecord | None:
    """Nearest sale whose schedule is knowable at T and that has not already ended."""
    if (
        target_event is not None
        and event_schedule_known_at(target_event, as_of=as_of)
        and target_event.end_date >= as_of
    ):
        return target_event
    candidates = [
        event
        for event in events
        if event.end_date >= as_of and event_schedule_known_at(event, as_of=as_of)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.start_date, item.id))
    return candidates[0]
