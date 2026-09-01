"""Deterministic BUY_NOW / WAIT / WATCH recommendation engine.

Combines current effective price, Phase 7 historical intelligence, Phase 9 upcoming sale
events, and optional Phase 10 XGBoost predictions. The engine does not train or invoke a
model, does not call a generative AI API, and never fabricates prices, savings, events, or
confidence. Phase 10 prediction confidence is never copied as recommendation confidence.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal

from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.enums import FreshnessStatus, TrendDirection, ValueKind
from app.pricing.freshness import classify_freshness, utc_now
from app.pricing.history_models import CalculatedMetric, VariantHistory
from app.pricing.money import quantize_ratio
from app.recommendation.config import (
    RECOMMENDATION_DISCLAIMER,
    RecommendationConfig,
    get_recommendation_config,
)
from app.recommendation.enums import (
    BuyingWindow,
    InsufficientRecommendationReason,
    Recommendation,
    RuleId,
    Urgency,
)
from app.recommendation.models import (
    EvidenceSnapshot,
    OpportunitySnapshot,
    OptionalMetric,
    PredictionInput,
    RecommendationInput,
    RecommendationResult,
    UpcomingSaleInput,
)
from app.recommendation.rules import (
    current_price,
    evaluate_buy_signals,
    evaluate_gates,
    evaluate_phase19_windows,
    evaluate_prediction_usability,
    evaluate_wait_signals,
    evaluate_watch_signals,
    metric_value,
    predicted_savings,
    select_credible_upcoming,
    strongly_favorable_from,
    wait_evidence_from,
    weakly_favorable_from,
)

logger = get_logger(__name__)

RECOMMENDATION_DECISIONS = "recommendation.decisions"

_CONF_CURRENT = Decimal("0.20")
_CONF_PERCENTILE = Decimal("0.15")
_CONF_LOW = Decimal("0.10")
_CONF_AVG = Decimal("0.10")
_CONF_TREND = Decimal("0.05")
_CONF_FRESH = Decimal("0.15")
_CONF_AGING = Decimal("0.07")
_CONF_PRED_CAP = Decimal("0.10")
_CONF_EVENT = Decimal("0.05")
_CONF_CONFLICT = Decimal("0.75")
_CONF_INSUFFICIENT = Decimal("0.50")


def _optional_from_calculated(metric: CalculatedMetric, *, value_kind: ValueKind) -> OptionalMetric:
    return OptionalMetric(
        value=metric.value,
        value_kind=value_kind,
        status=metric.status,
        unit=metric.unit,
        observation_count=metric.observation_count,
        window_days=metric.window_days,
    )


def input_from_variant_history(
    history: VariantHistory,
    *,
    prediction: PredictionInput | None = None,
    upcoming_events: Sequence[UpcomingSaleInput] = (),
    as_of: datetime | None = None,
    pricing_config: PricingConfig | None = None,
    urgency: Urgency | None = None,
    ordinary_opportunity: OpportunitySnapshot | None = None,
    major_opportunity: OpportunitySnapshot | None = None,
) -> RecommendationInput:
    """Project Phase 7 variant history into engine input. Missing metrics stay None."""
    current = history.current_observation
    moment = as_of if as_of is not None else history.calculated_at
    if current is not None and current.effective_price is not None:
        price = current.effective_price
        kind = ValueKind.CALCULATED
        field = "effective_price"
    elif current is not None:
        price = current.displayed_price
        kind = ValueKind.OBSERVED
        field = "displayed_price"
    else:
        price = None
        kind = None
        field = None
    freshness = (
        FreshnessStatus.MISSING
        if current is None
        else classify_freshness(
            current.observed_at,
            as_of=moment,
            config=pricing_config if pricing_config is not None else get_pricing_config(),
        )
    )
    return RecommendationInput(
        as_of=moment,
        product_id=history.product_id,
        product_variant_id=history.product_variant_id,
        currency=current.currency if current is not None else "INR",
        current_effective_price=price,
        current_price_value_kind=kind,
        current_price_field=field,
        qualifying_observation_count=history.qualifying_observation_count,
        freshness_status=freshness,
        historical_percentile=_optional_from_calculated(
            history.current_price_percentile, value_kind=ValueKind.CALCULATED
        ),
        historical_low=_optional_from_calculated(
            history.historical_low, value_kind=ValueKind.CALCULATED
        ),
        average_30d=_optional_from_calculated(history.average_30d, value_kind=ValueKind.CALCULATED),
        average_90d=_optional_from_calculated(history.average_90d, value_kind=ValueKind.CALCULATED),
        trend_direction=history.trend.direction,
        prediction=prediction,
        upcoming_events=tuple(upcoming_events),
        urgency=urgency,
        ordinary_opportunity=ordinary_opportunity,
        major_opportunity=major_opportunity,
    )


def _recommendation_confidence(
    payload: RecommendationInput,
    *,
    prediction_used: bool,
    conflict: bool,
    decision: Recommendation,
    config: RecommendationConfig,
) -> float:
    """Evidence quality/completeness/freshness. Not Phase 10 prediction confidence."""
    score = Decimal("0")
    if payload.current_effective_price is not None:
        score += _CONF_CURRENT
    if metric_value(payload.historical_percentile) is not None:
        score += _CONF_PERCENTILE
    if metric_value(payload.historical_low) is not None:
        score += _CONF_LOW
    if metric_value(payload.average_30d) is not None:
        score += _CONF_AVG
    if metric_value(payload.average_90d) is not None:
        score += _CONF_AVG
    if (
        payload.trend_direction is not None
        and payload.trend_direction is not TrendDirection.INSUFFICIENT_HISTORY
    ):
        score += _CONF_TREND
    if payload.freshness_status is FreshnessStatus.FRESH:
        score += _CONF_FRESH
    elif payload.freshness_status is FreshnessStatus.AGING:
        score += _CONF_AGING
    if (
        prediction_used
        and payload.prediction is not None
        and payload.prediction.confidence is not None
    ):
        score += _CONF_PRED_CAP * Decimal(str(payload.prediction.confidence))
    if select_credible_upcoming(payload.upcoming_events, config) is not None:
        score += _CONF_EVENT
    if conflict:
        score *= _CONF_CONFLICT
    if decision is Recommendation.INSUFFICIENT_DATA:
        score *= _CONF_INSUFFICIENT
    clipped = min(Decimal("1"), max(Decimal("0"), quantize_ratio(score)))
    return float(clipped)


def _gate_reason_code(rule_id: RuleId) -> InsufficientRecommendationReason:
    mapping = {
        RuleId.GATE_NO_CURRENT_PRICE: InsufficientRecommendationReason.NO_CURRENT_PRICE,
        RuleId.GATE_STALE_DATA: InsufficientRecommendationReason.STALE_DATA,
        RuleId.GATE_MISSING_DATA: InsufficientRecommendationReason.MISSING_DATA,
        RuleId.GATE_INSUFFICIENT_HISTORY: InsufficientRecommendationReason.INSUFFICIENT_HISTORY,
    }
    return mapping[rule_id]


class RecommendationEngine:
    """Retailer-agnostic rule engine. Independent of FastAPI and of XGBoost."""

    def __init__(
        self,
        config: RecommendationConfig | None = None,
        *,
        metrics_sink: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config if config is not None else get_recommendation_config()
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now

    @property
    def config(self) -> RecommendationConfig:
        return self._config

    def recommend(self, payload: RecommendationInput) -> RecommendationResult:
        """Evaluate explicit rules and return an explainable, repeatable decision."""
        config = self._config
        gates = evaluate_gates(payload, config)
        fired_gates = tuple(rule for rule in gates if rule.fired)
        prediction_used, unused_pred_rules = evaluate_prediction_usability(payload, config)

        buy_rules = evaluate_buy_signals(payload, config, prediction_used=prediction_used)
        strongly = strongly_favorable_from(buy_rules)
        weakly = weakly_favorable_from(buy_rules, strongly)
        near_low = any(
            rule.fired
            and rule.rule_id
            in {RuleId.BUY_NEAR_HISTORICAL_LOW, RuleId.BUY_STRONG_NEAR_HISTORICAL_LOW}
            for rule in buy_rules
        )
        wait_rules = evaluate_wait_signals(
            payload,
            config,
            prediction_used=prediction_used,
            strongly_favorable=strongly,
            near_low=near_low,
        )
        wait_fired = wait_evidence_from(wait_rules)
        conflict = strongly and wait_fired
        watch_rules = evaluate_watch_signals(
            payload,
            config,
            strongly_favorable=strongly,
            weakly_favorable=weakly,
            wait_fired=wait_fired,
            conflict=conflict,
        )

        if fired_gates:
            decision = Recommendation.INSUFFICIENT_DATA
            insufficient = _gate_reason_code(fired_gates[0].rule_id)
            chosen = fired_gates
        elif conflict:
            decision = Recommendation.WATCH
            insufficient = None
            chosen = tuple(rule for rule in watch_rules if rule.fired) or watch_rules[:1]
        elif wait_fired:
            decision = Recommendation.WAIT
            insufficient = None
            chosen = tuple(rule for rule in wait_rules if rule.fired)
        elif strongly:
            decision = Recommendation.BUY_NOW
            insufficient = None
            chosen = tuple(
                rule
                for rule in buy_rules
                if rule.fired
                and rule.rule_id
                in {
                    RuleId.BUY_FAVORABLE_PERCENTILE,
                    RuleId.BUY_STRONG_PERCENTILE,
                    RuleId.BUY_NEAR_HISTORICAL_LOW,
                    RuleId.BUY_STRONG_NEAR_HISTORICAL_LOW,
                    RuleId.BUY_BELOW_AVERAGES,
                    RuleId.BUY_PREDICTION_NO_MATERIAL_SAVINGS,
                    RuleId.BUY_FALLING_TREND,
                }
            )
        else:
            decision = Recommendation.WATCH
            insufficient = None
            chosen = tuple(rule for rule in watch_rules if rule.fired)
            if not chosen:
                chosen = unused_pred_rules or watch_rules[:1]

        phase19_rules, buying_window, override = evaluate_phase19_windows(
            payload, config, strongly_favorable=strongly
        )
        if decision is not Recommendation.INSUFFICIENT_DATA and override is not None:
            decision = override
            fired_phase19 = tuple(rule for rule in phase19_rules if rule.fired)
            if fired_phase19:
                chosen = fired_phase19
        if buying_window is None:
            buying_window = {
                Recommendation.BUY_NOW: BuyingWindow.BUY_NOW,
                Recommendation.WAIT: BuyingWindow.WAIT,
                Recommendation.WATCH: BuyingWindow.WATCH,
                Recommendation.INSUFFICIENT_DATA: BuyingWindow.INSUFFICIENT_DATA,
            }[decision]

        expected_saving, saving_pct, saving_basis = self._expected_saving(
            payload,
            prediction_used=prediction_used,
            decision=decision,
            buying_window=buying_window,
        )
        confidence = _recommendation_confidence(
            payload,
            prediction_used=prediction_used,
            conflict=conflict,
            decision=decision,
            config=config,
        )
        evidence = self._evidence(
            payload,
            prediction_used=prediction_used,
            expected_saving_basis=saving_basis,
            buying_window=buying_window,
        )
        reasons = self._reasons(
            decision=decision,
            chosen=chosen,
            unused_pred_rules=unused_pred_rules,
            prediction_used=prediction_used,
            buying_window=buying_window,
            urgency=payload.urgency,
        )
        triggered = tuple(rule.rule_id for rule in chosen if rule.fired)
        evaluated = gates + unused_pred_rules + buy_rules + wait_rules + watch_rules + phase19_rules
        result = RecommendationResult(
            recommendation=decision,
            expected_saving=expected_saving,
            expected_saving_percentage=saving_pct,
            expected_saving_value_kind=ValueKind.CALCULATED
            if expected_saving is not None
            else None,
            confidence=confidence,
            reasons=reasons,
            triggered_rule_ids=triggered,
            disclaimer=RECOMMENDATION_DISCLAIMER,
            prediction_used=prediction_used,
            insufficient=insufficient,
            evidence=evidence,
            evaluated_rules=evaluated,
            buying_window=buying_window,
            urgency=payload.urgency,
            ordinary_opportunity=payload.ordinary_opportunity,
            major_opportunity=payload.major_opportunity,
            product_id=payload.product_id,
            product_variant_id=payload.product_variant_id,
            as_of=payload.as_of,
            currency=payload.currency,
        )
        self._metrics.increment(RECOMMENDATION_DECISIONS)
        logger.info(
            "recommendation.decision",
            extra={
                "product_id": str(payload.product_id),
                "product_variant_id": str(payload.product_variant_id),
                "recommendation": decision.value,
                "prediction_used": prediction_used,
                "expected_saving": str(expected_saving) if expected_saving is not None else None,
                "confidence": confidence,
                "triggered_rule_ids": [item.value for item in triggered],
            },
        )
        return result

    def _expected_saving(
        self,
        payload: RecommendationInput,
        *,
        prediction_used: bool,
        decision: Recommendation,
        buying_window: BuyingWindow,
    ) -> tuple[Decimal | None, Decimal | None, str | None]:
        """CALCULATED saving. Phase 19 windows used only when urgency selected them."""
        if buying_window is BuyingWindow.WAIT_FOR_MAJOR_SALE and payload.major_opportunity:
            opp = payload.major_opportunity
            if opp.expected_saving is not None:
                return (
                    opp.expected_saving,
                    opp.expected_saving_percentage,
                    "major_sale_expected_price_vs_current",
                )
        if buying_window is BuyingWindow.BUY_IN_ORDINARY_SALE and payload.ordinary_opportunity:
            opp = payload.ordinary_opportunity
            if opp.expected_saving is not None:
                return (
                    opp.expected_saving,
                    opp.expected_saving_percentage,
                    "ordinary_sale_expected_price_vs_current",
                )
        if not prediction_used or payload.prediction is None:
            return None, None, None
        amount, percent = predicted_savings(
            current_price(payload), payload.prediction.predicted_price
        )
        if amount is None:
            return None, None, None
        return amount, percent, "predicted_sale_price_vs_current"

    def _evidence(
        self,
        payload: RecommendationInput,
        *,
        prediction_used: bool,
        expected_saving_basis: str | None,
        buying_window: BuyingWindow | None,
    ) -> EvidenceSnapshot:
        upcoming = select_credible_upcoming(payload.upcoming_events, self._config)
        predicted = (
            payload.prediction.predicted_price
            if prediction_used and payload.prediction is not None
            else None
        )
        pred_conf = (
            payload.prediction.confidence
            if prediction_used and payload.prediction is not None
            else None
        )
        ordinary = payload.ordinary_opportunity
        major = payload.major_opportunity
        return EvidenceSnapshot(
            current_effective_price=payload.current_effective_price,
            current_price_value_kind=payload.current_price_value_kind,
            historical_percentile=metric_value(payload.historical_percentile),
            historical_low=metric_value(payload.historical_low),
            average_30d=metric_value(payload.average_30d),
            average_90d=metric_value(payload.average_90d),
            trend_direction=payload.trend_direction,
            predicted_sale_price=predicted,
            prediction_confidence=pred_conf,
            prediction_used=prediction_used,
            upcoming_sale_name=upcoming.name if upcoming is not None else None,
            upcoming_sale_days=upcoming.days_until_start if upcoming is not None else None,
            freshness_status=payload.freshness_status,
            qualifying_observation_count=payload.qualifying_observation_count,
            expected_saving_basis=expected_saving_basis,
            urgency=payload.urgency,
            buying_window=buying_window,
            ordinary_sale_name=ordinary.display_name if ordinary is not None else None,
            ordinary_sale_days=ordinary.days_until_start if ordinary is not None else None,
            major_sale_name=major.display_name if major is not None else None,
            major_sale_days=major.days_until_start if major is not None else None,
        )

    def _reasons(
        self,
        *,
        decision: Recommendation,
        chosen: tuple,
        unused_pred_rules: tuple,
        prediction_used: bool,
        buying_window: BuyingWindow | None,
        urgency: Urgency | None,
    ) -> tuple[str, ...]:
        lines: list[str] = [
            f"Recommendation is {decision.value}. This is not a guaranteed price or saving."
        ]
        if buying_window is not None:
            lines.append(
                f"Buying window is {buying_window.value}. Projected sale dates and prices "
                "are evidence-based estimates and are not guaranteed retailer announcements."
            )
        if urgency is not None:
            lines.append(f"Urgency input: {urgency.value}.")
        for rule in chosen:
            if rule.fired:
                lines.append(f"[{rule.rule_id.value}] {rule.reason}")
        if not prediction_used:
            for rule in unused_pred_rules:
                if rule.fired and rule.rule_id.value.startswith("PRED_UNUSED"):
                    lines.append(f"[{rule.rule_id.value}] {rule.reason}")
        lines.append(RECOMMENDATION_DISCLAIMER)
        return tuple(lines)
