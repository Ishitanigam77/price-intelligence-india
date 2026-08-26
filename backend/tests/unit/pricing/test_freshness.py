"""Observation freshness from real timestamps only."""

from datetime import timedelta

from app.pricing.config import PricingConfig
from app.pricing.enums import FreshnessStatus
from app.pricing.freshness import aggregate_freshness, classify_freshness, offer_freshness
from tests.unit.pricing.helpers import NOW


def _config() -> PricingConfig:
    return PricingConfig(_env_file=None, fresh_within_hours=6, stale_after_hours=24)


def test_fresh_aging_stale_and_missing() -> None:
    config = _config()
    assert classify_freshness(NOW, as_of=NOW, config=config) is FreshnessStatus.FRESH
    assert (
        classify_freshness(NOW - timedelta(hours=10), as_of=NOW, config=config)
        is FreshnessStatus.AGING
    )
    assert (
        classify_freshness(NOW - timedelta(hours=48), as_of=NOW, config=config)
        is FreshnessStatus.STALE
    )
    assert classify_freshness(None, as_of=NOW, config=config) is FreshnessStatus.MISSING


def test_offer_freshness_never_invents_a_timestamp() -> None:
    missing = offer_freshness(None, as_of=NOW, config=_config())
    assert missing.observed_at is None
    assert missing.age_seconds is None
    assert missing.status is FreshnessStatus.MISSING


def test_aggregate_freshness_uses_actual_min_max_timestamps() -> None:
    config = _config()
    older = offer_freshness(NOW - timedelta(hours=48), as_of=NOW, config=config)
    newer = offer_freshness(NOW - timedelta(hours=1), as_of=NOW, config=config)
    missing = offer_freshness(None, as_of=NOW, config=config)
    summary = aggregate_freshness((older, newer, missing), as_of=NOW)
    assert summary.oldest_observation == NOW - timedelta(hours=48)
    assert summary.newest_observation == NOW - timedelta(hours=1)
    assert summary.stale_offer_count == 1
    assert summary.missing_observation_count == 1
    assert summary.status is FreshnessStatus.STALE
