"""Deterministic exponential backoff with a hard cap. No infinite retry loops."""

from __future__ import annotations

from app.collectors.config import CollectionConfig
from app.collectors.errors import CollectionFailure
from app.domain.enums import CollectionErrorCategory

RETRYABLE_CATEGORIES: frozenset[CollectionErrorCategory] = frozenset(
    {
        CollectionErrorCategory.TIMEOUT,
        CollectionErrorCategory.RATE_LIMITED,
        CollectionErrorCategory.TEMPORARY_FAILURE,
    }
)


def is_retryable(error: CollectionFailure, *, attempt: int, max_attempts: int) -> bool:
    """Retry only retryable categories, and only while attempts remain."""
    if attempt >= max_attempts:
        return False
    return error.retryable and error.category in RETRYABLE_CATEGORIES


def backoff_seconds(config: CollectionConfig, *, attempt: int) -> float:
    """Delay after the 1-based failed `attempt`. Exponential, bounded, no jitter.

    Deterministic so tests can assert exact delays. Adapter-level jitter (if any) stays inside
    the retailer adapter executor and does not leak into this curve.
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    raw = config.initial_backoff_seconds * (config.backoff_multiplier ** (attempt - 1))
    return min(raw, config.max_backoff_seconds)
