"""Observation freshness derived only from real timestamps.

Never fabricates an observation time. A missing observation is `missing`, not "now".
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.pricing.config import PricingConfig
from app.pricing.enums import FreshnessStatus
from app.pricing.models import DataFreshness


def classify_freshness(
    observed_at: datetime | None,
    *,
    as_of: datetime,
    config: PricingConfig,
) -> FreshnessStatus:
    if observed_at is None:
        return FreshnessStatus.MISSING
    age_seconds = (as_of - observed_at).total_seconds()
    if age_seconds < 0:
        # Clock skew: an observation in the future is still a real timestamp; treat as fresh.
        return FreshnessStatus.FRESH
    if age_seconds <= config.fresh_within_seconds:
        return FreshnessStatus.FRESH
    if age_seconds <= config.stale_after_seconds:
        return FreshnessStatus.AGING
    return FreshnessStatus.STALE


def offer_freshness(
    observed_at: datetime | None,
    *,
    as_of: datetime,
    config: PricingConfig,
) -> DataFreshness:
    status = classify_freshness(observed_at, as_of=as_of, config=config)
    age = None if observed_at is None else (as_of - observed_at).total_seconds()
    return DataFreshness(
        status=status,
        as_of=as_of,
        observed_at=observed_at,
        age_seconds=age,
        oldest_observation=observed_at,
        newest_observation=observed_at,
        stale_offer_count=1 if status is FreshnessStatus.STALE else 0,
        missing_observation_count=1 if status is FreshnessStatus.MISSING else 0,
        offer_count=1,
    )


def aggregate_freshness(
    items: tuple[DataFreshness, ...],
    *,
    as_of: datetime,
) -> DataFreshness:
    """Combine per-offer freshness into a variant/product summary.

    Status is the worst of the members: missing > stale > aging > fresh. Timestamps are the
    actual min/max of observed times, never synthesized.
    """
    if not items:
        return DataFreshness(
            status=FreshnessStatus.MISSING,
            as_of=as_of,
            missing_observation_count=0,
            offer_count=0,
        )
    observed = [item.observed_at for item in items if item.observed_at is not None]
    stale_count = sum(item.stale_offer_count for item in items)
    missing_count = sum(item.missing_observation_count for item in items)
    statuses = {item.status for item in items}
    if FreshnessStatus.MISSING in statuses and not observed:
        status = FreshnessStatus.MISSING
    elif FreshnessStatus.STALE in statuses or stale_count > 0:
        status = FreshnessStatus.STALE
    elif FreshnessStatus.MISSING in statuses:
        status = FreshnessStatus.STALE
    elif FreshnessStatus.AGING in statuses:
        status = FreshnessStatus.AGING
    else:
        status = FreshnessStatus.FRESH
    oldest = min(observed) if observed else None
    newest = max(observed) if observed else None
    age = None if newest is None else (as_of - newest).total_seconds()
    return DataFreshness(
        status=status,
        as_of=as_of,
        observed_at=newest,
        age_seconds=age,
        oldest_observation=oldest,
        newest_observation=newest,
        stale_offer_count=stale_count,
        missing_observation_count=missing_count,
        offer_count=sum(item.offer_count for item in items),
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
