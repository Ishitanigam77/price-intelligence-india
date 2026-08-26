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
