"""Price comparison engine: verified effective price, freshness, and deterministic ranking.

Independent of FastAPI routes and of specific retailer adapter packages. Callers supply
`OfferInput` values already projected from persisted listings/snapshots.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from app.domain.enums import AdjustmentKind, ConfidenceLevel
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.effective import (
    amount_for_kind,
    can_win_verified_ranking,
    classify_price_kind,
    collect_offer_adjustments,
    compute_effective_price,
    displayed_discount_percentage,
    is_offer_available,
    resolve_offer_confidence,
)
from app.pricing.enums import PriceKind
from app.pricing.freshness import aggregate_freshness, offer_freshness, utc_now
from app.pricing.models import (
    ComparedOffer,
    OfferInput,
    ProductComparison,
    VariantComparison,
)
from app.pricing.ranking import rank_offers, select_lowest_verified

logger = get_logger(__name__)

COMPARISON_VARIANTS = "pricing.comparison.variants"
COMPARISON_OFFERS = "pricing.comparison.offers"


class PriceComparisonEngine:
    """Compare retailer offers for matched product variants using deterministic rules."""

    def __init__(
        self,
        config: PricingConfig | None = None,
        *,
        metrics_sink: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config if config is not None else get_pricing_config()
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now

    @property
    def config(self) -> PricingConfig:
        return self._config

    def compare_variant(
        self,
        variant_id: uuid.UUID,
        offers: Sequence[OfferInput],
        *,
        variant_key: str | None = None,
        as_of: datetime | None = None,
    ) -> VariantComparison:
        """Rank offers for a single variant. Never includes offers from other variants."""
        now = as_of if as_of is not None else self._clock()
        built = tuple(self._build_offer(offer, as_of=now) for offer in offers)
        ranked = rank_offers(built)
        winner, explanation = select_lowest_verified(ranked)
        freshness = aggregate_freshness(tuple(offer.freshness for offer in ranked), as_of=now)
        self._metrics.increment(COMPARISON_VARIANTS)
        self._metrics.increment(COMPARISON_OFFERS, value=len(ranked))
        logger.info(
            "pricing.variant_compared",
            extra={
                "variant_id": str(variant_id),
                "offer_count": len(ranked),
                "lowest_verified_offer_id": explanation.selected_offer_id,
                "ranking_criterion": explanation.criterion.value,
                "freshness": freshness.status.value,
            },
        )
        return VariantComparison(
            variant_id=variant_id,
            variant_key=variant_key,
            offers=ranked,
            lowest_verified_offer=winner,
            ranking=explanation,
            data_freshness=freshness,
        )

    def compare_product(
        self,
        product_id: uuid.UUID,
        variants: Mapping[uuid.UUID, Sequence[OfferInput]],
        *,
        variant_keys: Mapping[uuid.UUID, str] | None = None,
        as_of: datetime | None = None,
    ) -> ProductComparison:
        """Compare offers per variant of a product. Variants are never combined."""
        now = as_of if as_of is not None else self._clock()
        keys = variant_keys or {}
        comparisons = tuple(
            self.compare_variant(
                variant_id,
                offers,
                variant_key=keys.get(variant_id),
                as_of=now,
            )
            for variant_id, offers in variants.items()
        )
        freshness = aggregate_freshness(
            tuple(item.data_freshness for item in comparisons), as_of=now
        )
        logger.info(
            "pricing.product_compared",
            extra={
                "product_id": str(product_id),
                "variant_count": len(comparisons),
                "offer_count": sum(len(item.offers) for item in comparisons),
                "freshness": freshness.status.value,
            },
        )
        return ProductComparison(
            product_id=product_id,
            variants=comparisons,
            data_freshness=freshness,
            as_of=now,
        )

    def _build_offer(self, offer: OfferInput, *, as_of: datetime) -> ComparedOffer:
        adjustments = collect_offer_adjustments(offer)
        freshness = offer_freshness(offer.observed_at, as_of=as_of, config=self._config)
        verified = compute_effective_price(offer.displayed_price, adjustments)
        estimated = compute_effective_price(
            offer.displayed_price, adjustments, include_unverified=True
        )
        if estimated == verified:
            estimated = None
        price_kind = classify_price_kind(
            displayed_price=offer.displayed_price,
            verified_effective=verified,
            adjustments=adjustments,
        )
        available = is_offer_available(offer.availability)
        confidence = resolve_offer_confidence(offer, adjustments, freshness.status)
        if offer.observation_confidence is None and offer.observed_at is None:
            confidence = ConfidenceLevel.LOW
        return ComparedOffer(
            offer_id=offer.offer_id,
            variant_id=offer.variant_id,
            retailer_id=offer.retailer_id,
            retailer_slug=offer.retailer_slug,
            retailer_name=offer.retailer_name,
            retailer_product_id=offer.retailer_product_id,
            seller=offer.seller,
            displayed_price=offer.displayed_price,
            mrp=offer.mrp,
            discount_percentage=displayed_discount_percentage(offer.mrp, offer.displayed_price),
            coupon_discount=amount_for_kind(adjustments, AdjustmentKind.COUPON),
            payment_discount=amount_for_kind(adjustments, AdjustmentKind.PAYMENT_DISCOUNT),
            cashback=amount_for_kind(adjustments, AdjustmentKind.CASHBACK),
            delivery_fee=offer.delivery_fee,
            platform_fee=offer.platform_fee,
            effective_price=verified,
            unverified_estimated_price=estimated,
            unverified_price_kind=PriceKind.ESTIMATED_UNVERIFIED if estimated is not None else None,
            source_effective_price=offer.source_effective_price,
            price_kind=price_kind,
            availability=offer.availability,
            source_url=offer.source_url,
            source_type=offer.source_type,
            observation_timestamp=offer.observed_at,
            confidence=confidence,
            observation_confidence=offer.observation_confidence,
            freshness=freshness,
            adjustments=adjustments,
            currency=offer.currency,
            rank=0,
            is_available=available,
            can_win_verified_ranking=can_win_verified_ranking(
                is_available=available,
                displayed_price=offer.displayed_price,
                verified_effective=verified,
            ),
        )
