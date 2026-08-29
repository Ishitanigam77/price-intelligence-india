"""Projecting Phase 7 history into recommendation input, and Phase 10 contract stability."""

from datetime import timedelta
from decimal import Decimal
from inspect import signature

from app.pricing.config import PricingConfig
from app.pricing.enums import FreshnessStatus, ValueKind
from app.recommendation.engine import RecommendationEngine, input_from_variant_history
from app.services.sale_price_prediction_service import SalePricePredictionService
from ml.inference.predict import predict, predict_listing
from tests.unit.pricing.helpers import NOW, VARIANT_A, history_engine, history_point
from tests.unit.recommendation.helpers import rec_config


def test_input_from_variant_history_uses_current_observation_freshness_not_old_points() -> None:
    product_id = history_point().product_id
    listing_id = history_point().retailer_product_id
    points = [
        history_point(
            product_id=product_id,
            listing_id=listing_id,
            displayed_price="200.00",
            effective_price="200.00",
            observed_at=NOW - timedelta(days=10),
        ),
        history_point(
            product_id=product_id,
            listing_id=listing_id,
            displayed_price="150.00",
            effective_price="150.00",
            observed_at=NOW - timedelta(days=5),
        ),
        history_point(
            product_id=product_id,
            listing_id=listing_id,
            displayed_price="100.00",
            effective_price="100.00",
            observed_at=NOW - timedelta(hours=1),
        ),
    ]
    history = history_engine().compute_variant(
        product_id=product_id,
        product_variant_id=VARIANT_A,
        observations=points,
        as_of=NOW,
    )
    # Aggregate history freshness is stale because of 10-day-old points.
    assert history.data_freshness.status is FreshnessStatus.STALE
    payload = input_from_variant_history(
        history,
        as_of=NOW,
        pricing_config=PricingConfig(_env_file=None),
    )
    assert payload.freshness_status is FreshnessStatus.FRESH
    assert payload.current_effective_price == Decimal("100.00")
    assert payload.current_price_value_kind is ValueKind.CALCULATED
    result = RecommendationEngine(config=rec_config(), clock=lambda: NOW).recommend(payload)
    assert result.recommendation.value != "INSUFFICIENT_DATA"


def test_phase10_prediction_service_and_inference_entrypoints_are_unchanged() -> None:
    """Phase 11 consumes Phase 10; it must not replace train/predict signatures."""
    assert callable(predict)
    assert callable(predict_listing)
    params = signature(SalePricePredictionService.predict_product).parameters
    assert "product_id" in params
    assert "variant_id" in params
    assert "as_of" in params
    assert "model_version" in params
    inference_params = signature(predict).parameters
    assert "points" in inference_params
    assert "events" in inference_params
    assert "as_of" in inference_params
    assert "artifact_root" in inference_params
