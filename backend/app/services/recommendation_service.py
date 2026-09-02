"""Recommendation service: history + sale events + Phase 10 prediction → rule engine.

Projects stored observations into Phase 7 history, loads applicable Phase 9 events, calls
the existing Phase 10 `SalePricePredictionService` without modifying or retraining the
model, and asks `RecommendationEngine` for a deterministic BUY_NOW / WAIT / WATCH decision.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.db.models import PriceSnapshot, Product, ProductVariant
from app.domain.enums import ConfidenceLevel
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.freshness import utc_now
from app.pricing.history import PriceHistoryEngine
from app.pricing.history_models import HistoricalObservationPoint
from app.recommendation.config import RecommendationConfig, get_recommendation_config
from app.recommendation.engine import RecommendationEngine, input_from_variant_history
from app.recommendation.enums import Urgency
from app.recommendation.models import OpportunitySnapshot, PredictionInput, UpcomingSaleInput
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.sale_event_repository import SaleEventRepository
from app.sales.engine import SaleEventEngine
from app.sales.timing_models import SaleOpportunity
from app.schemas.prediction import SalePricePredictionRead
from app.schemas.recommendation import ProductRecommendationRead, product_recommendation_read
from app.services.sale_event_service import SaleEventService
from app.services.sale_intelligence_service import SaleIntelligenceService
from app.services.sale_price_prediction_service import SalePricePredictionService

logger = get_logger(__name__)

_SECONDS_PER_DAY = 86400.0


class RecommendationService:
    """Orchestrates persistence → engines → API schema for one product."""

    def __init__(
        self,
        session: Session,
        *,
        metrics_sink: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
        recommendation_config: RecommendationConfig | None = None,
        pricing_config: PricingConfig | None = None,
        history_engine: PriceHistoryEngine | None = None,
        sale_engine: SaleEventEngine | None = None,
        recommendation_engine: RecommendationEngine | None = None,
        prediction_service: SalePricePredictionService | None = None,
        intelligence_service: SaleIntelligenceService | None = None,
    ) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._variants = ProductVariantRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._events = SaleEventRepository(session)
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now
        self._pricing_config = (
            pricing_config if pricing_config is not None else get_pricing_config()
        )
        rec_config = (
            recommendation_config
            if recommendation_config is not None
            else get_recommendation_config()
        )
        self._history = history_engine or PriceHistoryEngine(
            config=self._pricing_config,
            metrics_sink=self._metrics,
            clock=self._clock,
        )
        self._sales = sale_engine or SaleEventEngine(
            metrics_sink=self._metrics,
            clock=self._clock,
        )
        self._engine = recommendation_engine or RecommendationEngine(
            config=rec_config,
            metrics_sink=self._metrics,
            clock=self._clock,
        )
        self._prediction = prediction_service or SalePricePredictionService(
            session,
            metrics_sink=self._metrics,
            clock=self._clock,
        )
        self._intelligence = intelligence_service or SaleIntelligenceService(
            session,
            metrics_sink=self._metrics,
            clock=self._clock,
            prediction_service=self._prediction,
        )

    def recommend_product(
        self,
        product_id: uuid.UUID,
        *,
        variant_id: uuid.UUID | None = None,
        as_of: datetime | None = None,
        model_version: str | None = None,
        urgency: Urgency | None = None,
    ) -> ProductRecommendationRead:
        product = self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")

        at = as_of if as_of is not None else self._clock()
        variants = self._variants.list_for_product(product_id)
        if variant_id is not None:
            variants = [variant for variant in variants if variant.id == variant_id]
            if not variants:
                raise NotFoundError(
                    f"Product variant {variant_id} was not found on product {product_id}."
                )

        predictions = self._prediction.predict_product(
            product_id,
            variant_id=variant_id,
            as_of=at,
            model_version=model_version,
        )
        events = [
            SaleEventService._record(row)
            for row in self._events.list_applicable_to_product(
                brand_id=product.brand_id, category_id=product.category_id
            )
        ]
        upcoming_views = self._sales.upcoming(events, at=at)
        upcoming = tuple(
            UpcomingSaleInput(
                event_id=view.event.id,
                name=view.event.name,
                start_date=view.event.start_date,
                end_date=view.event.end_date,
                confidence=view.event.confidence,
                source=view.event.source,
                status=view.status,
                days_until_start=_days_until(view.event.start_date, at=at),
            )
            for view in upcoming_views
        )

        snapshots = self._snapshots.history_for_product(product_id, variant_id=variant_id)
        points_by_variant: dict[uuid.UUID, list[HistoricalObservationPoint]] = {
            variant.id: [] for variant in variants
        }
        for snapshot in snapshots:
            listing = snapshot.retailer_product
            variant = listing.product_variant
            if variant.id not in points_by_variant:
                continue
            points_by_variant[variant.id].append(
                self._point_from_snapshot(snapshot, product=product, variant=variant)
            )

        variant_keys = {variant.id: variant.variant_key for variant in variants}
        history = self._history.compute_product(
            product_id,
            points_by_variant,
            variant_keys=variant_keys,
            as_of=at,
        )
        intelligence = self._intelligence.compute_product(
            product,
            variants,
            as_of=at,
            model_version=model_version,
            variant_id=variant_id,
        )
        intel_by_variant = {item.product_variant_id: item for item in intelligence.variants}

        results = []
        for variant_history in history.variants:
            prediction_input = _prediction_for_current(
                predictions.predictions, variant_history.current_observation
            )
            intel = intel_by_variant.get(variant_history.product_variant_id)
            payload = input_from_variant_history(
                variant_history,
                prediction=prediction_input,
                upcoming_events=upcoming,
                as_of=at,
                pricing_config=self._pricing_config,
                urgency=urgency,
                ordinary_opportunity=(
                    _opportunity_snapshot(intel.ordinary) if intel is not None else None
                ),
                major_opportunity=_opportunity_snapshot(intel.major) if intel is not None else None,
            )
            results.append(self._engine.recommend(payload))

        logger.info(
            "recommendation.product_completed",
            extra={
                "product_id": str(product_id),
                "variant_count": len(results),
                "as_of": at.isoformat(),
                "phase10_status": predictions.status.value,
            },
        )
        return product_recommendation_read(
            product_id=product_id,
            as_of=at,
            phase10_status=predictions.status.value,
            phase10_model_version=predictions.model_version,
            results=results,
        )

    @staticmethod
    def _point_from_snapshot(
        snapshot: PriceSnapshot,
        *,
        product: Product,
        variant: ProductVariant,
    ) -> HistoricalObservationPoint:
        listing = snapshot.retailer_product
        retailer = listing.retailer
        return HistoricalObservationPoint(
            snapshot_id=snapshot.id,
            product_id=product.id,
            product_variant_id=variant.id,
            variant_key=variant.variant_key,
            retailer_id=listing.retailer_id,
            retailer_slug=retailer.slug,
            retailer_name=retailer.name,
            retailer_product_id=listing.id,
            seller_id=snapshot.seller_id,
            source_url=snapshot.source_url or listing.url,
            source_type=snapshot.source_type,
            observed_at=snapshot.observed_at,
            created_at=snapshot.created_at,
            currency=snapshot.currency,
            displayed_price=snapshot.displayed_price,
            effective_price=snapshot.effective_price,
            mrp=snapshot.mrp,
            availability=snapshot.availability,
            confidence=snapshot.confidence,
        )


_CONFIDENCE_FLOAT = {
    ConfidenceLevel.HIGH: 0.85,
    ConfidenceLevel.MEDIUM: 0.60,
    ConfidenceLevel.LOW: 0.35,
}


def _opportunity_snapshot(opportunity: SaleOpportunity | None) -> OpportunitySnapshot | None:
    """Project a Phase 19 opportunity into the recommendation engine. Never invents prices."""
    if opportunity is None:
        return None
    confidence = None
    if opportunity.confidence is not None:
        confidence = _CONFIDENCE_FLOAT.get(opportunity.confidence)
    return OpportunitySnapshot(
        sale_type=opportunity.sale_type.value,
        display_name=opportunity.window.display_name,
        evidence_status=opportunity.window.evidence_status.value,
        expected_start_date=opportunity.window.expected_start_date,
        expected_end_date=opportunity.window.expected_end_date,
        days_until_start=opportunity.days_until_start,
        expected_price=opportunity.expected_price,
        expected_price_value_kind=opportunity.expected_price_value_kind,
        expected_saving=opportunity.expected_saving,
        expected_saving_percentage=opportunity.expected_saving_percentage,
        expected_saving_value_kind=opportunity.expected_saving_value_kind,
        likely_best_retailer_name=opportunity.likely_best_retailer_name,
        confidence=confidence,
        historical_reliability=(
            opportunity.historical_reliability.value
            if opportunity.historical_reliability is not None
            else None
        ),
        status=opportunity.status.value,
    )


def _days_until(start: datetime, *, at: datetime) -> int:
    seconds = (start - at).total_seconds()
    if seconds <= 0:
        return 0
    return int(seconds // _SECONDS_PER_DAY)


def _prediction_for_current(
    predictions: list[SalePricePredictionRead],
    current: HistoricalObservationPoint | None,
) -> PredictionInput | None:
    """Bind a listing-level Phase 10 prediction to this variant's current observation.

    Another listing's prediction is never reused. A missing match means prediction is unused.
    """
    if current is None:
        return None
    match: SalePricePredictionRead | None = None
    for item in predictions:
        if (
            item.product_variant_id == current.product_variant_id
            and item.retailer_id == current.retailer_id
            and item.seller_id == current.seller_id
        ):
            match = item
            break
    if match is None:
        return None
    insufficient = match.insufficient.reason if match.insufficient is not None else None
    return PredictionInput(
        status=match.status.value,
        predicted_price=match.predicted_price,
        confidence=match.confidence,
        insufficient_reason=insufficient,
        product_variant_id=match.product_variant_id,
        retailer_id=match.retailer_id,
        seller_id=match.seller_id,
        model_version=match.model_version,
    )
