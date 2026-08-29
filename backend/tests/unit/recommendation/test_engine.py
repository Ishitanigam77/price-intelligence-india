"""Deterministic BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA decisions."""

from decimal import Decimal

from app.domain.enums import ConfidenceLevel, SaleEventSource
from app.pricing.enums import FreshnessStatus, TrendDirection, ValueKind
from app.recommendation.config import RECOMMENDATION_DISCLAIMER
from app.recommendation.enums import InsufficientRecommendationReason, Recommendation, RuleId
from tests.unit.recommendation.helpers import (
    calculated,
    engine,
    payload,
    prediction,
    upcoming,
)


def _reasons(result) -> str:
    return " ".join(result.reasons)


def test_buy_now_from_favorable_percentile_and_historical_low() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("10.00", unit="percentile"),
            historical_low=calculated("98.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("150.00", window_days=90),
            trend_direction=TrendDirection.FALLING,
        )
    )
    assert result.recommendation is Recommendation.BUY_NOW
    assert result.expected_saving is None
    assert result.prediction_used is False
    assert RuleId.BUY_FAVORABLE_PERCENTILE in result.triggered_rule_ids
    assert RuleId.BUY_NEAR_HISTORICAL_LOW in result.triggered_rule_ids
    assert "10.00" in _reasons(result)
    assert "98.00" in _reasons(result)
    assert "not a guarantee" in _reasons(result).lower()
    assert result.disclaimer == RECOMMENDATION_DISCLAIMER
    assert result.evidence.current_price_value_kind is ValueKind.CALCULATED
    assert result.evidence.historical_percentile == Decimal("10.00")


def test_wait_from_unfavorable_historical_percentile() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("200.00"),
            historical_percentile=calculated("85.00", unit="percentile"),
            historical_low=calculated("100.00"),
            average_30d=calculated("120.00", window_days=30),
            average_90d=calculated("130.00", window_days=90),
            trend_direction=TrendDirection.RISING,
        )
    )
    assert result.recommendation is Recommendation.WAIT
    assert result.expected_saving is None
    assert RuleId.WAIT_UNFAVORABLE_PERCENTILE in result.triggered_rule_ids
    assert "85.00" in _reasons(result)
    assert "WAIT threshold" in _reasons(result)


def test_wait_when_predicted_price_is_materially_below_current() -> None:
    pred = prediction(price="150.00", confidence=0.82)
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("200.00"),
            historical_percentile=calculated("45.00", unit="percentile"),
            historical_low=calculated("140.00"),
            average_30d=calculated("195.00", window_days=30),
            average_90d=calculated("198.00", window_days=90),
            prediction=pred,
        )
    )
    assert result.recommendation is Recommendation.WAIT
    assert result.prediction_used is True
    assert result.expected_saving == Decimal("50.00")
    assert result.expected_saving_value_kind is ValueKind.CALCULATED
    assert result.evidence.expected_saving_basis == "predicted_sale_price_vs_current"
    assert result.evidence.predicted_sale_price == Decimal("150.00")
    assert RuleId.WAIT_PREDICTED_SAVINGS in result.triggered_rule_ids
    assert "PREDICTED" in _reasons(result)
    assert "50.00" in _reasons(result)
    assert result.confidence != pred.confidence


def test_watch_when_evidence_is_neutral() -> None:
    result = engine().recommend(payload())
    assert result.recommendation is Recommendation.WATCH
    assert result.expected_saving is None
    assert RuleId.WATCH_NEUTRAL_HISTORY in result.triggered_rule_ids
    assert "neutral" in _reasons(result).lower()


def test_insufficient_data_when_current_price_missing() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=None,
            current_price_value_kind=None,
            current_price_field=None,
        )
    )
    assert result.recommendation is Recommendation.INSUFFICIENT_DATA
    assert result.insufficient is InsufficientRecommendationReason.NO_CURRENT_PRICE
    assert result.expected_saving is None
    assert RuleId.GATE_NO_CURRENT_PRICE in result.triggered_rule_ids
    assert "not invented" in _reasons(result).lower()


def test_insufficient_data_when_observation_is_stale() -> None:
    result = engine().recommend(payload(freshness_status=FreshnessStatus.STALE))
    assert result.recommendation is Recommendation.INSUFFICIENT_DATA
    assert result.insufficient is InsufficientRecommendationReason.STALE_DATA
    assert RuleId.GATE_STALE_DATA in result.triggered_rule_ids
    assert result.expected_saving is None


def test_insufficient_data_when_freshness_is_missing() -> None:
    result = engine().recommend(payload(freshness_status=FreshnessStatus.MISSING))
    assert result.recommendation is Recommendation.INSUFFICIENT_DATA
    assert result.insufficient is InsufficientRecommendationReason.MISSING_DATA


def test_insufficient_data_when_historical_observations_are_too_few() -> None:
    result = engine().recommend(
        payload(
            qualifying_observation_count=1,
            historical_percentile=calculated(None, unit="percentile"),
            historical_low=calculated("100.00"),
        )
    )
    assert result.recommendation is Recommendation.INSUFFICIENT_DATA
    assert result.insufficient is InsufficientRecommendationReason.INSUFFICIENT_HISTORY
    assert RuleId.GATE_INSUFFICIENT_HISTORY in result.triggered_rule_ids
    assert "not fabricated" in _reasons(result).lower()


def test_missing_prediction_falls_back_to_historical_buy_now() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("12.00", unit="percentile"),
            historical_low=calculated("99.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("145.00", window_days=90),
            prediction=None,
        )
    )
    assert result.recommendation is Recommendation.BUY_NOW
    assert result.prediction_used is False
    assert result.expected_saving is None
    assert result.evidence.predicted_sale_price is None
    assert "PRED_UNUSED_MISSING" in _reasons(result)
    assert "not invented" in _reasons(result).lower()


def test_low_prediction_confidence_is_unused_not_copied() -> None:
    pred = prediction(price="80.00", confidence=0.20)
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("150.00"),
            historical_percentile=calculated("45.00", unit="percentile"),
            prediction=pred,
        )
    )
    assert result.recommendation is Recommendation.WATCH
    assert result.prediction_used is False
    assert result.expected_saving is None
    assert result.evidence.predicted_sale_price is None
    assert result.confidence != 0.20
    assert "PRED_UNUSED_LOW_CONFIDENCE" in _reasons(result)
    assert RuleId.WATCH_PREDICTION_LOW_CONFIDENCE in {
        item.rule_id for item in result.evaluated_rules if item.fired
    }


def test_insufficient_phase10_prediction_is_unused() -> None:
    pred = prediction(
        price=None,
        confidence=None,
        status="INSUFFICIENT_DATA",
        reason="No trained sale-price model is available.",
    )
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("12.00", unit="percentile"),
            historical_low=calculated("99.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("145.00", window_days=90),
            prediction=pred,
        )
    )
    assert result.recommendation is Recommendation.BUY_NOW
    assert result.prediction_used is False
    assert result.expected_saving is None
    assert "PRED_UNUSED_INSUFFICIENT" in _reasons(result)


def test_upcoming_sale_event_supports_wait_when_price_is_not_a_strong_buy() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("200.00"),
            historical_percentile=calculated("60.00", unit="percentile"),
            historical_low=calculated("100.00"),
            average_30d=calculated("150.00", window_days=30),
            average_90d=calculated("155.00", window_days=90),
            upcoming_events=(upcoming(days=5),),
        )
    )
    assert result.recommendation is Recommendation.WAIT
    assert result.expected_saving is None
    assert RuleId.WAIT_UPCOMING_SALE in result.triggered_rule_ids
    assert "FIXTURE: Fictional Seasonal Sale" in _reasons(result)
    assert result.evidence.upcoming_sale_days == 5


def test_low_confidence_upcoming_event_is_watch_not_wait() -> None:
    result = engine().recommend(
        payload(
            upcoming_events=(
                upcoming(confidence=ConfidenceLevel.LOW, name="FIXTURE: Weak inferred window"),
            )
        )
    )
    assert result.recommendation is Recommendation.WATCH
    assert RuleId.WAIT_UPCOMING_SALE not in result.triggered_rule_ids
    fired = {item.rule_id for item in result.evaluated_rules if item.fired}
    assert RuleId.WATCH_EVENT_NOT_CREDIBLE in fired


def test_inferred_upcoming_event_is_not_credible_wait_evidence() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("150.00"),
            historical_percentile=calculated("55.00", unit="percentile"),
            historical_low=calculated("100.00"),
            average_30d=calculated("148.00", window_days=30),
            average_90d=calculated("152.00", window_days=90),
            upcoming_events=(
                upcoming(
                    source=SaleEventSource.OBSERVED_PRICE_INFERENCE,
                    name="FIXTURE: Calculated drop window",
                ),
            ),
        )
    )
    assert RuleId.WAIT_UPCOMING_SALE not in result.triggered_rule_ids
    assert result.recommendation is Recommendation.WATCH


def test_conflicting_buy_and_predicted_savings_is_watch() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("8.00", unit="percentile"),
            historical_low=calculated("99.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("145.00", window_days=90),
            prediction=prediction(price="70.00", confidence=0.88),
        )
    )
    assert result.recommendation is Recommendation.WATCH
    assert RuleId.WATCH_CONFLICTING_SIGNALS in result.triggered_rule_ids
    assert "mixed" in _reasons(result).lower()
    assert result.expected_saving == Decimal("30.00")
    assert result.prediction_used is True


def test_expected_saving_is_not_fabricated_without_usable_prediction() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("200.00"),
            historical_percentile=calculated("90.00", unit="percentile"),
            historical_low=calculated("100.00"),
        )
    )
    assert result.recommendation is Recommendation.WAIT
    assert result.expected_saving is None
    assert result.evidence.expected_saving_basis is None
    assert result.evidence.predicted_sale_price is None


def test_predicted_price_above_current_does_not_create_negative_saving() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("12.00", unit="percentile"),
            historical_low=calculated("99.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("145.00", window_days=90),
            prediction=prediction(price="120.00", confidence=0.9),
        )
    )
    assert result.recommendation is Recommendation.BUY_NOW
    assert result.expected_saving is None
    assert result.prediction_used is True
    assert RuleId.BUY_PREDICTION_NO_MATERIAL_SAVINGS in result.triggered_rule_ids


def test_missing_historical_metrics_are_not_zero_filled() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("150.00"),
            historical_percentile=calculated(None, unit="percentile"),
            historical_low=calculated(None),
            average_30d=calculated(None, window_days=30),
            average_90d=calculated(None, window_days=90),
            trend_direction=TrendDirection.INSUFFICIENT_HISTORY,
            qualifying_observation_count=3,
        )
    )
    assert result.evidence.historical_percentile is None
    assert result.evidence.historical_low is None
    assert result.evidence.average_30d is None
    assert result.evidence.average_90d is None
    assert result.expected_saving is None
    assert result.recommendation is Recommendation.WATCH


def test_output_is_deterministic_and_repeatable() -> None:
    item = payload(
        current_effective_price=Decimal("100.00"),
        historical_percentile=calculated("12.00", unit="percentile"),
        historical_low=calculated("99.00"),
        average_30d=calculated("140.00", window_days=30),
        average_90d=calculated("145.00", window_days=90),
        prediction=prediction(price="97.00", confidence=0.7),
    )
    first = engine().recommend(item)
    second = engine().recommend(item)
    assert first.model_dump() == second.model_dump()


def test_phase10_prediction_input_is_not_mutated() -> None:
    pred = prediction(price="80.00", confidence=0.77)
    original_price = pred.predicted_price
    original_confidence = pred.confidence
    engine().recommend(payload(prediction=pred))
    assert pred.predicted_price == original_price
    assert pred.confidence == original_confidence
    assert pred.value_kind is ValueKind.PREDICTED
    assert pred.is_prediction is True


def test_recommendation_confidence_is_not_phase10_confidence() -> None:
    pred = prediction(price="180.00", confidence=0.99)
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("200.00"),
            historical_percentile=calculated("80.00", unit="percentile"),
            historical_low=calculated("100.00"),
            prediction=pred,
        )
    )
    assert result.prediction_used is True
    assert result.confidence is not None
    assert result.confidence != 0.99
    assert 0.0 <= result.confidence <= 1.0


def test_aging_data_is_usable_but_not_treated_as_fresh() -> None:
    fresh = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("12.00", unit="percentile"),
            historical_low=calculated("99.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("145.00", window_days=90),
            freshness_status=FreshnessStatus.FRESH,
        )
    )
    aging = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("12.00", unit="percentile"),
            historical_low=calculated("99.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("145.00", window_days=90),
            freshness_status=FreshnessStatus.AGING,
        )
    )
    assert aging.recommendation is Recommendation.BUY_NOW
    assert aging.recommendation == fresh.recommendation
    assert aging.confidence is not None and fresh.confidence is not None
    assert aging.confidence < fresh.confidence


def test_reasons_cite_triggered_rule_ids() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("200.00"),
            historical_percentile=calculated("88.00", unit="percentile"),
            historical_low=calculated("90.00"),
        )
    )
    for rule_id in result.triggered_rule_ids:
        assert f"[{rule_id.value}]" in _reasons(result)
