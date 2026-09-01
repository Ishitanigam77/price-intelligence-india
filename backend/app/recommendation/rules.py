"""Explicit, documented recommendation rules.

Every decision is the composition of these rules against available inputs. No LLM or ML
model is a decision maker here. Phase 10 predictions are optional labeled inputs; when they
are missing or below the confidence threshold they are ignored and never invented.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.enums import ConfidenceLevel, SaleEventSource, SaleEventStatus
from app.pricing.enums import FreshnessStatus, MetricStatus, TrendDirection, ValueKind
from app.pricing.money import quantize_money, quantize_ratio
from app.recommendation.config import RecommendationConfig
from app.recommendation.enums import BuyingWindow, Recommendation, RuleId, Urgency
from app.recommendation.models import (
    EvaluatedRule,
    OpportunitySnapshot,
    OptionalMetric,
    PredictionInput,
    RecommendationInput,
    UpcomingSaleInput,
)

_HUNDRED = Decimal("100")
_ONE = Decimal("1")
PREDICTED_STATUS = "PREDICTED"


def metric_value(metric: OptionalMetric | None) -> Decimal | None:
    """Return a CALCULATED metric value only when it was actually computed."""
    if metric is None:
        return None
    if metric.status is not MetricStatus.AVAILABLE or metric.value is None:
        return None
    return metric.value


def _dec(value: float) -> Decimal:
    return Decimal(str(value))


def _money_reason(amount: Decimal, currency: str) -> str:
    return f"{amount:.2f} {currency}"


def _percent_reason(value: Decimal) -> str:
    return f"{value:.2f}"


def current_price(payload: RecommendationInput) -> Decimal | None:
    return payload.current_effective_price


def is_near_historical_low(
    current: Decimal | None,
    historical_low: Decimal | None,
    percent: float,
) -> bool:
    if current is None or historical_low is None or historical_low < 0:
        return False
    ceiling = quantize_money(historical_low * (_ONE + _dec(percent) / _HUNDRED))
    return current <= ceiling


def percent_above(current: Decimal, baseline: Decimal) -> Decimal | None:
    if baseline <= 0:
        return None
    return quantize_ratio((current - baseline) / baseline * _HUNDRED)


def predicted_savings(
    current: Decimal | None,
    predicted: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Return (amount, percent of current). Never invents a predicted price."""
    if current is None or predicted is None or current <= 0:
        return None, None
    if predicted >= current:
        return None, None
    amount = quantize_money(current - predicted)
    percent = quantize_ratio(amount / current * _HUNDRED)
    return amount, percent


def prediction_is_usable(
    prediction: PredictionInput | None,
    config: RecommendationConfig,
) -> bool:
    if prediction is None:
        return False
    if prediction.status != PREDICTED_STATUS:
        return False
    if prediction.predicted_price is None:
        return False
    if prediction.value_kind is not ValueKind.PREDICTED:
        return False
    if prediction.confidence is None:
        return False
    return prediction.confidence >= config.min_prediction_confidence


def select_credible_upcoming(
    events: tuple[UpcomingSaleInput, ...],
    config: RecommendationConfig,
) -> UpcomingSaleInput | None:
    """Nearest HIGH/MEDIUM curated-or-permitted upcoming event inside the horizon.

    Inferred (`observed_price_inference`) windows are never treated as known upcoming sales.
    """
    credible = [
        event
        for event in events
        if event.status is SaleEventStatus.BEFORE_EVENT
        and event.source is not SaleEventSource.OBSERVED_PRICE_INFERENCE
        and event.confidence in {ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM}
        and event.days_until_start <= config.upcoming_horizon_days
    ]
    if not credible:
        return None
    credible.sort(key=lambda item: (item.days_until_start, item.start_date, item.event_id))
    return credible[0]


def _rule(
    rule_id: RuleId,
    fired: bool,
    reason: str,
    supports: Recommendation | None,
) -> EvaluatedRule:
    return EvaluatedRule(rule_id=rule_id, fired=fired, reason=reason, supports=supports)


def evaluate_gates(
    payload: RecommendationInput,
    config: RecommendationConfig,
) -> tuple[EvaluatedRule, ...]:
    """Hard stops. Any fired gate yields INSUFFICIENT_DATA — no guessed recommendation."""
    current = current_price(payload)
    currency = payload.currency
    no_price = current is None
    stale = payload.freshness_status is FreshnessStatus.STALE
    missing = payload.freshness_status is FreshnessStatus.MISSING
    short_history = payload.qualifying_observation_count < config.min_observations

    price_reason = (
        "No usable current effective price is available (neither a stored effective_price "
        "nor an observed displayed_price on a qualifying current observation). A price is "
        "not invented."
        if no_price
        else (
            f"Current price {_money_reason(current, currency)} is present "
            f"({payload.current_price_value_kind} {payload.current_price_field})."
        )
    )
    stale_reason = (
        "Current observation freshness is stale, so a buy/wait decision is not produced "
        f"(status={payload.freshness_status.value})."
        if stale
        else f"Current observation freshness is {payload.freshness_status.value}, not stale."
    )
    missing_reason = (
        "Current observation freshness is missing (no observation timestamp), so a "
        "buy/wait decision is not produced."
        if missing
        else f"Current observation freshness is {payload.freshness_status.value}, not missing."
    )
    history_reason = (
        "Qualifying historical observations are insufficient for a reliable decision "
        f"({payload.qualifying_observation_count} observation(s); "
        f"{config.min_observations} required). Missing history is not fabricated."
        if short_history
        else (
            f"Qualifying historical observations ({payload.qualifying_observation_count}) "
            f"meet the minimum of {config.min_observations}."
        )
    )
    return (
        _rule(
            RuleId.GATE_NO_CURRENT_PRICE, no_price, price_reason, Recommendation.INSUFFICIENT_DATA
        ),
        _rule(RuleId.GATE_STALE_DATA, stale, stale_reason, Recommendation.INSUFFICIENT_DATA),
        _rule(RuleId.GATE_MISSING_DATA, missing, missing_reason, Recommendation.INSUFFICIENT_DATA),
        _rule(
            RuleId.GATE_INSUFFICIENT_HISTORY,
            short_history,
            history_reason,
            Recommendation.INSUFFICIENT_DATA,
        ),
    )


def evaluate_prediction_usability(
    payload: RecommendationInput,
    config: RecommendationConfig,
) -> tuple[bool, tuple[EvaluatedRule, ...]]:
    """Whether Phase 10 output may enter WAIT/BUY evidence. Low confidence is unused."""
    prediction = payload.prediction
    unused_rules: list[EvaluatedRule] = []
    if prediction is None:
        unused_rules.append(
            _rule(
                RuleId.PRED_UNUSED_MISSING,
                True,
                "Phase 10 prediction is absent. The decision uses historical and "
                "current-price signals only; a predicted sale price is not invented.",
                Recommendation.WATCH,
            )
        )
        unused_rules.append(
            _rule(
                RuleId.WATCH_PREDICTION_MISSING,
                True,
                "No Phase 10 prediction was supplied, so predicted-price evidence is not used.",
                Recommendation.WATCH,
            )
        )
        return False, tuple(unused_rules)
    if prediction.status != PREDICTED_STATUS:
        unused_rules.append(
            _rule(
                RuleId.PRED_UNUSED_INSUFFICIENT,
                True,
                "Phase 10 prediction status is "
                f"{prediction.status} ({prediction.insufficient_reason or 'no predicted price'}). "
                "The decision falls back to historical and current-price signals; a predicted "
                "sale price is not invented.",
                Recommendation.WATCH,
            )
        )
        return False, tuple(unused_rules)
    if prediction.predicted_price is None:
        unused_rules.append(
            _rule(
                RuleId.PRED_UNUSED_NO_PRICE,
                True,
                "Phase 10 returned PREDICTED status without a predicted_price. "
                "A sale price is not invented.",
                Recommendation.WATCH,
            )
        )
        return False, tuple(unused_rules)
    if prediction.confidence is None or prediction.confidence < config.min_prediction_confidence:
        displayed = "none" if prediction.confidence is None else f"{prediction.confidence:.4f}"
        unused_rules.append(
            _rule(
                RuleId.PRED_UNUSED_LOW_CONFIDENCE,
                True,
                "Phase 10 prediction confidence "
                f"{displayed} is below the recommendation threshold "
                f"{config.min_prediction_confidence:.2f}. The predicted price "
                f"{_money_reason(prediction.predicted_price, payload.currency)} "
                "(PREDICTED) is unused, not copied as recommendation confidence, and not "
                "replaced with a fabricated value.",
                Recommendation.WATCH,
            )
        )
        unused_rules.append(
            _rule(
                RuleId.WATCH_PREDICTION_LOW_CONFIDENCE,
                True,
                "Prediction confidence is low/moderate relative to the recommendation "
                f"threshold ({config.min_prediction_confidence:.2f}), so predicted-price "
                "evidence is insufficient for WAIT.",
                Recommendation.WATCH,
            )
        )
        return False, tuple(unused_rules)
    return True, ()


def evaluate_buy_signals(
    payload: RecommendationInput,
    config: RecommendationConfig,
    *,
    prediction_used: bool,
) -> tuple[EvaluatedRule, ...]:
    current = current_price(payload)
    currency = payload.currency
    percentile = metric_value(payload.historical_percentile)
    historical_low = metric_value(payload.historical_low)
    avg_30 = metric_value(payload.average_30d)
    avg_90 = metric_value(payload.average_90d)
    prediction = payload.prediction if prediction_used else None
    predicted_price = prediction.predicted_price if prediction is not None else None

    favorable_percentile = percentile is not None and percentile <= _dec(config.buy_percentile_max)
    strong_percentile = percentile is not None and percentile <= _dec(
        config.buy_strong_percentile_max
    )
    near_low = is_near_historical_low(current, historical_low, config.near_historical_low_percent)
    strong_near_low = is_near_historical_low(
        current, historical_low, config.near_historical_low_strong_percent
    )
    below_30 = current is not None and avg_30 is not None and current <= avg_30
    below_90 = current is not None and avg_90 is not None and current <= avg_90
    below_both = below_30 and below_90
    _amount, savings_pct = predicted_savings(current, predicted_price)
    no_material_predicted_savings = prediction_used and (
        savings_pct is None or savings_pct < _dec(config.min_predicted_savings_percent)
    )
    falling = payload.trend_direction is TrendDirection.FALLING

    percentile_text = (
        (
            f"Current effective price {_money_reason(current, currency)} is at CALCULATED "
            f"historical percentile {_percent_reason(percentile)} "
            f"(BUY_NOW threshold ≤ {config.buy_percentile_max:.2f})."
        )
        if current is not None and percentile is not None
        else "Historical percentile is unavailable; this BUY_NOW percentile rule did not fire."
    )
    strong_percentile_text = (
        (
            f"CALCULATED historical percentile {_percent_reason(percentile)} is at or below "
            f"the strong-buy threshold {config.buy_strong_percentile_max:.2f}."
        )
        if percentile is not None and strong_percentile
        else (
            "Historical percentile is not at or below the strong-buy threshold "
            f"{config.buy_strong_percentile_max:.2f}."
        )
    )
    if current is not None and historical_low is not None:
        near_text = (
            f"Current effective price {_money_reason(current, currency)} is within "
            f"{config.near_historical_low_percent:.2f}% of CALCULATED historical low "
            f"{_money_reason(historical_low, currency)}."
        )
        strong_near_text = (
            f"Current effective price {_money_reason(current, currency)} is within "
            f"{config.near_historical_low_strong_percent:.2f}% of CALCULATED historical low "
            f"{_money_reason(historical_low, currency)}."
        )
    else:
        near_text = "Historical low is unavailable; the near-low BUY_NOW rule did not fire."
        strong_near_text = near_text
    if current is not None and avg_30 is not None and avg_90 is not None:
        averages_text = (
            f"Current effective price {_money_reason(current, currency)} is at or below "
            f"CALCULATED 30-day average {_money_reason(avg_30, currency)} and 90-day average "
            f"{_money_reason(avg_90, currency)}."
        )
    else:
        averages_text = (
            "30-day and/or 90-day CALCULATED averages are unavailable; the below-averages "
            "BUY_NOW rule did not fire."
        )
    if prediction_used and predicted_price is not None and current is not None:
        pred_text = (
            f"Usable Phase 10 predicted sale price {_money_reason(predicted_price, currency)} "
            f"(PREDICTED, confidence {prediction.confidence:.4f}) is not materially below "
            f"current {_money_reason(current, currency)} "
            f"(material-savings threshold {config.min_predicted_savings_percent:.2f}%)."
        )
    else:
        pred_text = (
            "Phase 10 prediction was not used as BUY_NOW confirmation "
            "(missing, insufficient, or below confidence threshold)."
        )
    trend_text = (
        "CALCULATED historical trend is falling, which supports a BUY_NOW reading of "
        "the current price. This is a historical description, not a forecast."
        if falling
        else (
            f"CALCULATED historical trend is {payload.trend_direction}; this is not a BUY_NOW rule."
        )
        if payload.trend_direction is not None
        else "Historical trend is unavailable; the falling-trend BUY_NOW rule did not fire."
    )

    return (
        _rule(
            RuleId.BUY_FAVORABLE_PERCENTILE,
            favorable_percentile,
            percentile_text,
            Recommendation.BUY_NOW,
        ),
        _rule(
            RuleId.BUY_STRONG_PERCENTILE,
            strong_percentile,
            strong_percentile_text,
            Recommendation.BUY_NOW,
        ),
        _rule(
            RuleId.BUY_NEAR_HISTORICAL_LOW,
            near_low,
            near_text,
            Recommendation.BUY_NOW,
        ),
        _rule(
            RuleId.BUY_STRONG_NEAR_HISTORICAL_LOW,
            strong_near_low,
            strong_near_text,
            Recommendation.BUY_NOW,
        ),
        _rule(
            RuleId.BUY_BELOW_AVERAGES,
            below_both,
            averages_text,
            Recommendation.BUY_NOW,
        ),
        _rule(
            RuleId.BUY_PREDICTION_NO_MATERIAL_SAVINGS,
            no_material_predicted_savings,
            pred_text,
            Recommendation.BUY_NOW,
        ),
        _rule(
            RuleId.BUY_FALLING_TREND,
            falling and (favorable_percentile or near_low or below_both),
            trend_text,
            Recommendation.BUY_NOW,
        ),
    )


def evaluate_wait_signals(
    payload: RecommendationInput,
    config: RecommendationConfig,
    *,
    prediction_used: bool,
    strongly_favorable: bool,
    near_low: bool,
) -> tuple[EvaluatedRule, ...]:
    current = current_price(payload)
    currency = payload.currency
    percentile = metric_value(payload.historical_percentile)
    avg_30 = metric_value(payload.average_30d)
    avg_90 = metric_value(payload.average_90d)
    prediction = payload.prediction if prediction_used else None
    predicted_price = prediction.predicted_price if prediction is not None else None
    amount, savings_pct = predicted_savings(current, predicted_price)
    material_predicted = savings_pct is not None and savings_pct >= _dec(
        config.min_predicted_savings_percent
    )
    unfavorable = (
        percentile is not None and percentile >= _dec(config.wait_percentile_min) and not near_low
    )
    above_30 = False
    above_90 = False
    if current is not None and avg_30 is not None and avg_30 > 0:
        gap = percent_above(current, avg_30)
        above_30 = gap is not None and gap >= _dec(config.min_above_average_percent)
    if current is not None and avg_90 is not None and avg_90 > 0:
        gap = percent_above(current, avg_90)
        above_90 = gap is not None and gap >= _dec(config.min_above_average_percent)
    above_averages = above_30 and (above_90 or avg_90 is None)
    rising = payload.trend_direction is TrendDirection.RISING
    upcoming = select_credible_upcoming(payload.upcoming_events, config)
    event_wait = upcoming is not None and not strongly_favorable

    if current is not None and percentile is not None:
        unfav_text = (
            f"Current effective price {_money_reason(current, currency)} is at CALCULATED "
            f"historical percentile {_percent_reason(percentile)} "
            f"(WAIT threshold ≥ {config.wait_percentile_min:.2f}), so it is materially "
            "above historical norms."
        )
    else:
        unfav_text = "Historical percentile is unavailable or not unfavorably high."
    if current is not None and avg_30 is not None:
        above_text = (
            f"Current effective price {_money_reason(current, currency)} is at least "
            f"{config.min_above_average_percent:.2f}% above CALCULATED 30-day average "
            f"{_money_reason(avg_30, currency)}"
            + (
                f" and 90-day average {_money_reason(avg_90, currency)}."
                if avg_90 is not None
                else "."
            )
        )
    else:
        above_text = "Window averages are unavailable; the above-averages WAIT rule did not fire."
    if (
        material_predicted
        and current is not None
        and predicted_price is not None
        and amount is not None
    ):
        pred_text = (
            f"Usable Phase 10 predicted sale price {_money_reason(predicted_price, currency)} "
            f"(PREDICTED, confidence {prediction.confidence:.4f}) is materially below current "
            f"{_money_reason(current, currency)}: calculated expected saving "
            f"{_money_reason(amount, currency)} ({_percent_reason(savings_pct)}% ≥ "
            f"{config.min_predicted_savings_percent:.2f}%). This saving is calculated from "
            "the labeled prediction, not observed."
        )
    else:
        pred_text = (
            "No usable Phase 10 prediction shows a material saving versus the current price."
        )
    if upcoming is not None:
        event_text = (
            f"Credible upcoming sale event {upcoming.name!r} starts in "
            f"{upcoming.days_until_start} day(s) (confidence={upcoming.confidence.value}, "
            f"source={upcoming.source.value}, horizon≤{config.upcoming_horizon_days} days)."
            + (
                " Current price is not strongly favorable, so waiting for that window is "
                "supported. Expected saving is omitted because no usable predicted or "
                "observed future price exists for that event."
                if event_wait
                else " Current price is already strongly favorable, so the event alone is "
                "not WAIT evidence."
            )
        )
    else:
        event_text = "No credible upcoming sale event is in horizon for WAIT evidence."
    trend_text = (
        "CALCULATED historical trend is rising and the current price is not strongly "
        "favorable, which supports WAIT. This is a historical description, not a forecast."
        if rising and not strongly_favorable
        else "CALCULATED historical trend is not a standalone WAIT trigger."
    )

    return (
        _rule(
            RuleId.WAIT_UNFAVORABLE_PERCENTILE,
            unfavorable,
            unfav_text,
            Recommendation.WAIT,
        ),
        _rule(
            RuleId.WAIT_ABOVE_AVERAGES,
            above_averages,
            above_text,
            Recommendation.WAIT,
        ),
        _rule(
            RuleId.WAIT_PREDICTED_SAVINGS,
            material_predicted,
            pred_text,
            Recommendation.WAIT,
        ),
        _rule(
            RuleId.WAIT_UPCOMING_SALE,
            event_wait,
            event_text,
            Recommendation.WAIT,
        ),
        _rule(
            RuleId.WAIT_RISING_TREND,
            rising and (unfavorable or above_averages or event_wait),
            trend_text,
            Recommendation.WAIT,
        ),
    )


def evaluate_watch_signals(
    payload: RecommendationInput,
    config: RecommendationConfig,
    *,
    strongly_favorable: bool,
    weakly_favorable: bool,
    wait_fired: bool,
    conflict: bool,
) -> tuple[EvaluatedRule, ...]:
    percentile = metric_value(payload.historical_percentile)
    buy_max = _dec(config.buy_percentile_max)
    wait_min = _dec(config.wait_percentile_min)
    neutral_percentile = (
        percentile is not None and buy_max < percentile < wait_min and not strongly_favorable
    )
    stable = payload.trend_direction is TrendDirection.STABLE
    weak_events = [
        event
        for event in payload.upcoming_events
        if event.status is SaleEventStatus.BEFORE_EVENT
        and (
            event.confidence is ConfidenceLevel.LOW
            or event.source is SaleEventSource.OBSERVED_PRICE_INFERENCE
            or event.days_until_start > config.upcoming_horizon_days
        )
    ]
    event_not_credible = (
        bool(weak_events) and select_credible_upcoming(payload.upcoming_events, config) is None
    )

    conflict_text = (
        "BUY_NOW historical signals and WAIT signals both fired. Evidence is mixed, so "
        "the decision is WATCH rather than forcing BUY_NOW or WAIT."
        if conflict
        else "BUY_NOW and WAIT signals are not both present."
    )
    neutral_text = (
        (
            f"CALCULATED historical percentile {_percent_reason(percentile)} is between "
            f"the BUY_NOW threshold {config.buy_percentile_max:.2f} and the WAIT threshold "
            f"{config.wait_percentile_min:.2f} (neutral historical position)."
        )
        if percentile is not None and neutral_percentile
        else "Historical percentile is not in the neutral band, or is unavailable."
    )
    weak_text = (
        "Historical position is only weakly favorable and WAIT evidence is not strong "
        "enough, so the decision is WATCH."
        if weakly_favorable and not wait_fired
        else "Weak-favorable WATCH rule did not fire."
    )
    event_text = (
        "An upcoming sale-related window exists but is not credible WAIT evidence "
        f"(low confidence, inferred source, or outside {config.upcoming_horizon_days}-day "
        "horizon)."
        if event_not_credible
        else "No weak/non-credible upcoming event needs a WATCH note."
    )
    trend_text = (
        "CALCULATED historical trend is stable/neutral, which is insufficient for BUY_NOW "
        "or WAIT on its own."
        if stable and not strongly_favorable and not wait_fired
        else "Trend is not a standalone WATCH trigger."
    )
    return (
        _rule(
            RuleId.WATCH_CONFLICTING_SIGNALS,
            conflict,
            conflict_text,
            Recommendation.WATCH,
        ),
        _rule(
            RuleId.WATCH_NEUTRAL_HISTORY,
            neutral_percentile and not wait_fired and not strongly_favorable,
            neutral_text,
            Recommendation.WATCH,
        ),
        _rule(
            RuleId.WATCH_WEAK_FAVORABLE,
            weakly_favorable and not wait_fired,
            weak_text,
            Recommendation.WATCH,
        ),
        _rule(
            RuleId.WATCH_EVENT_NOT_CREDIBLE,
            event_not_credible and not wait_fired,
            event_text,
            Recommendation.WATCH,
        ),
        _rule(
            RuleId.WATCH_NEUTRAL_TREND,
            stable and not strongly_favorable and not wait_fired,
            trend_text,
            Recommendation.WATCH,
        ),
    )


def strongly_favorable_from(buy_rules: tuple[EvaluatedRule, ...]) -> bool:
    fired = {item.rule_id for item in buy_rules if item.fired}
    if RuleId.BUY_STRONG_PERCENTILE in fired or RuleId.BUY_STRONG_NEAR_HISTORICAL_LOW in fired:
        return True
    if RuleId.BUY_FAVORABLE_PERCENTILE in fired and RuleId.BUY_NEAR_HISTORICAL_LOW in fired:
        return True
    return RuleId.BUY_FAVORABLE_PERCENTILE in fired and RuleId.BUY_BELOW_AVERAGES in fired


def weakly_favorable_from(buy_rules: tuple[EvaluatedRule, ...], strongly: bool) -> bool:
    if strongly:
        return False
    fired = {item.rule_id for item in buy_rules if item.fired}
    return bool(
        fired
        & {
            RuleId.BUY_FAVORABLE_PERCENTILE,
            RuleId.BUY_NEAR_HISTORICAL_LOW,
            RuleId.BUY_BELOW_AVERAGES,
        }
    )


def wait_evidence_from(wait_rules: tuple[EvaluatedRule, ...]) -> bool:
    fired = {item.rule_id for item in wait_rules if item.fired}
    return bool(
        fired
        & {
            RuleId.WAIT_UNFAVORABLE_PERCENTILE,
            RuleId.WAIT_ABOVE_AVERAGES,
            RuleId.WAIT_PREDICTED_SAVINGS,
            RuleId.WAIT_UPCOMING_SALE,
        }
    )


def _opportunity_usable(
    snapshot: OpportunitySnapshot | None,
    config: RecommendationConfig,
) -> bool:
    if snapshot is None:
        return False
    if snapshot.status == "insufficient_history":
        return False
    if snapshot.expected_price is None or snapshot.days_until_start is None:
        return False
    if snapshot.expected_saving is None or snapshot.expected_saving_percentage is None:
        return False
    return snapshot.expected_saving_percentage >= _dec(config.min_predicted_savings_percent)


def _major_worthwhile(
    payload: RecommendationInput,
    config: RecommendationConfig,
    *,
    ordinary_ok: bool,
    major_ok: bool,
) -> bool:
    major = payload.major_opportunity
    ordinary = payload.ordinary_opportunity
    if not major_ok or major is None:
        return False
    if major.days_until_start is None or major.days_until_start > config.patient_horizon_days:
        return False
    if not ordinary_ok or ordinary is None or ordinary.expected_saving is None:
        return (major.expected_saving_percentage or Decimal("0")) >= _dec(
            config.min_predicted_savings_percent
        )
    extra = (major.expected_saving or Decimal("0")) - ordinary.expected_saving
    current = current_price(payload)
    extra_pct = (
        quantize_ratio(extra / current * _HUNDRED)
        if current is not None and current > 0 and extra > 0
        else None
    )
    if extra_pct is not None and extra_pct >= _dec(config.min_additional_major_savings_percent):
        return True
    return extra > 0 and (major.expected_saving_percentage or Decimal("0")) >= _dec(
        config.min_predicted_savings_percent
    )


def evaluate_phase19_windows(
    payload: RecommendationInput,
    config: RecommendationConfig,
    *,
    strongly_favorable: bool,
) -> tuple[tuple[EvaluatedRule, ...], BuyingWindow | None, Recommendation | None]:
    """Urgency-aware ordinary vs major choice. No-op when urgency is absent."""
    if payload.urgency is None:
        return (), None, None
    ordinary = payload.ordinary_opportunity
    major = payload.major_opportunity
    ordinary_ok = _opportunity_usable(ordinary, config)
    major_ok = _opportunity_usable(major, config)
    ordinary_days = ordinary.days_until_start if ordinary is not None else None
    major_days = major.days_until_start if major is not None else None

    if payload.urgency is Urgency.URGENT:
        ordinary_soon = (
            ordinary_ok
            and ordinary_days is not None
            and ordinary_days <= config.urgent_horizon_days
        )
        major_soon = (
            major_ok and major_days is not None and major_days <= config.urgent_horizon_days
        )
        ordinary_rule = _rule(
            RuleId.WAIT_ORDINARY_SALE_SOON,
            ordinary_soon and not strongly_favorable,
            (
                f"Urgency is urgent. An ordinary sale is {ordinary_days} day(s) away with "
                f"expected saving {ordinary.expected_saving} {payload.currency} "
                f"({ordinary.expected_saving_percentage}%). Waiting several weeks for a "
                "major sale is not recommended for an urgent purchase."
                if ordinary is not None and ordinary_soon
                else "No ordinary sale is soon enough for an urgent purchase."
            ),
            Recommendation.WAIT,
        )
        major_rule = _rule(
            RuleId.WAIT_MAJOR_SALE_WORTHWHILE,
            major_soon and not ordinary_soon and not strongly_favorable,
            (
                f"Urgency is urgent and a major sale is {major_days} day(s) away."
                if major_soon
                else "Major sale is not inside the urgent horizon."
            ),
            Recommendation.WAIT,
        )
        rules = (ordinary_rule, major_rule)
        if strongly_favorable:
            return rules, BuyingWindow.BUY_NOW, None
        if ordinary_rule.fired:
            return rules, BuyingWindow.BUY_IN_ORDINARY_SALE, Recommendation.WAIT
        if major_rule.fired:
            return rules, BuyingWindow.WAIT_FOR_MAJOR_SALE, Recommendation.WAIT
        return rules, BuyingWindow.BUY_NOW, Recommendation.BUY_NOW

    worthwhile = _major_worthwhile(payload, config, ordinary_ok=ordinary_ok, major_ok=major_ok)
    major_rule = _rule(
        RuleId.WAIT_MAJOR_SALE_WORTHWHILE,
        worthwhile,
        (
            f"Urgency is patient. A major sale is {major_days} day(s) away with expected "
            f"saving {major.expected_saving} {payload.currency} "
            f"({major.expected_saving_percentage}%). Additional waiting is treated as "
            "worthwhile from absolute and percentage savings, not an arbitrary price cutoff."
            if worthwhile and major is not None
            else "Major-sale waiting is not worthwhile from available savings evidence."
        ),
        Recommendation.WAIT,
    )
    ordinary_rule = _rule(
        RuleId.WAIT_ORDINARY_SALE_SOON,
        ordinary_ok and not worthwhile,
        (
            f"Urgency is patient. An ordinary sale is {ordinary_days} day(s) away."
            if ordinary_ok
            else "No usable ordinary-sale opportunity."
        ),
        Recommendation.WAIT,
    )
    rules = (ordinary_rule, major_rule)
    if major_rule.fired:
        return rules, BuyingWindow.WAIT_FOR_MAJOR_SALE, Recommendation.WAIT
    if ordinary_rule.fired:
        return rules, BuyingWindow.BUY_IN_ORDINARY_SALE, Recommendation.WAIT
    return rules, None, None
