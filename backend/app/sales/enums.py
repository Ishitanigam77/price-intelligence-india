"""Enumerations owned by sale-event intelligence.

Persisted event type/source/status live in `app.domain.enums` because they appear on `SaleEvent`
rows (status is derived, but it is a domain concept of the entity). The values below are
analysis-output concepts and are not stored.
"""

from enum import StrEnum


class SaleInsufficientReasonCode(StrEnum):
    """Machine-readable reason a sale-history calculation was withheld rather than fabricated."""

    NO_QUALIFYING_OBSERVATIONS = "no_qualifying_observations"
    NO_APPLICABLE_EVENTS = "no_applicable_events"
    NO_OBSERVATIONS_DURING_EVENT = "no_observations_during_event"
    BELOW_MINIMUM_OBSERVATION_COUNT = "below_minimum_observation_count"
    ZERO_BASELINE_PRICE = "zero_baseline_price"
    INSUFFICIENT_LISTINGS_FOR_DETECTION = "insufficient_listings_for_detection"
