"""Enumerations owned by the price comparison engine.

Adjustment kind/eligibility live in `app.domain.enums` because they are persisted on
`PriceAdjustment` rows. The values below are comparison-output concepts and are not stored.
"""

from enum import StrEnum


class PriceKind(StrEnum):
    """How an offer's payable price should be interpreted.

    These three states must never be collapsed into a single ambiguous "price" field
    (`PROJECT_ARCHITECTURE.md` §6).
    """

    VERIFIED_EFFECTIVE = "verified_effective"
    DISPLAYED_ONLY = "displayed_only"
    ESTIMATED_UNVERIFIED = "estimated_unverified"


class FreshnessStatus(StrEnum):
    """Freshness of a price observation relative to a configured staleness window."""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    MISSING = "missing"


class RankingCriterion(StrEnum):
    """Deterministic ranking keys, in the order they are applied.

    The selected offer's `ranking_reason` always names the criterion that decided the result.
    """

    VERIFIED_EFFECTIVE_PRICE = "verified_effective_price"
    DISPLAYED_PRICE = "displayed_price"
    AVAILABILITY = "availability"
    SELLER_QUALITY = "seller_quality"
    DELIVERY = "delivery"
    NO_APPLICABLE_OFFER = "no_applicable_offer"


class ValueKind(StrEnum):
    """Provenance label for a numeric value (`PROJECT_ARCHITECTURE.md` §6).

    Phase 7 historical intelligence returns OBSERVED points and CALCULATED aggregates.
    PREDICTED is defined so callers can assert it is never produced here (Phase 8).
    """

    OBSERVED = "OBSERVED"
    CALCULATED = "CALCULATED"
    PREDICTED = "PREDICTED"


class MetricStatus(StrEnum):
    """Whether a historical aggregate could be computed from stored observations."""

    AVAILABLE = "available"
    INSUFFICIENT_HISTORY = "insufficient_history"


class InsufficientReasonCode(StrEnum):
    """Machine-readable reason a calculation was withheld rather than fabricated."""

    NO_QUALIFYING_OBSERVATIONS = "no_qualifying_observations"
    NO_OBSERVATIONS_IN_WINDOW = "no_observations_in_window"
    BELOW_MINIMUM_OBSERVATION_COUNT = "below_minimum_observation_count"
    NO_CURRENT_PRICE = "no_current_price"
    NO_COMPARISON_BASELINE = "no_comparison_baseline"
    ZERO_TIME_SPAN = "zero_time_span"
    ZERO_BASELINE_PRICE = "zero_baseline_price"


class TrendDirection(StrEnum):
    """Deterministic historical trend from observed prices. Not a forecast."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    INSUFFICIENT_HISTORY = "insufficient_history"
