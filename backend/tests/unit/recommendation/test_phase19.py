"""Phase 19 urgency overlay on the existing Phase 11 recommendation engine."""

from decimal import Decimal

from app.pricing.enums import TrendDirection, ValueKind
from app.recommendation.enums import BuyingWindow, Recommendation, RuleId, Urgency
from app.recommendation.models import OpportunitySnapshot
from tests.unit.recommendation.helpers import calculated, engine, payload, prediction, upcoming


def opportunity(**overrides: object) -> OpportunitySnapshot:
    values: dict[str, object] = {
        "sale_type": "ORDINARY",
        "display_name": "FIXTURE: Fictional Ordinary Sale",
        "evidence_status": "expected",
        "days_until_start": 7,
        "expected_price": Decimal("47500.00"),
        "expected_price_value_kind": ValueKind.CALCULATED,
        "expected_saving": Decimal("2500.00"),
        "expected_saving_percentage": Decimal("5.00"),
        "expected_saving_value_kind": ValueKind.CALCULATED,
        "likely_best_retailer_name": "Fictional Mart A",
        "confidence": 0.60,
        "historical_reliability": "medium",
        "status": "available",
    }
    values.update(overrides)
    return OpportunitySnapshot(**values)  # type: ignore[arg-type]


def _neutral_expensive() -> dict[str, object]:
    return {
        "current_effective_price": Decimal("50000.00"),
        "historical_percentile": calculated("45.00", unit="percentile"),
        "historical_low": calculated("40000.00"),
        "average_30d": calculated("49800.00", window_days=30),
        "average_90d": calculated("50100.00", window_days=90),
        "trend_direction": TrendDirection.STABLE,
        "ordinary_opportunity": opportunity(),
        "major_opportunity": opportunity(
            sale_type="MAJOR",
            display_name="FIXTURE: Fictional Major Sale",
            days_until_start=40,
            expected_price=Decimal("43000.00"),
            expected_saving=Decimal("7000.00"),
            expected_saving_percentage=Decimal("14.00"),
            confidence=0.80,
            historical_reliability="high",
        ),
    }


def test_no_urgency_preserves_phase11_decision() -> None:
    result = engine().recommend(payload(**_neutral_expensive()))
    assert result.recommendation is Recommendation.WATCH
    assert result.buying_window is BuyingWindow.WATCH
    assert result.urgency is None
    assert result.ordinary_opportunity is not None
    assert result.major_opportunity is not None


def test_urgent_prefers_soon_ordinary_sale() -> None:
    result = engine().recommend(payload(urgency=Urgency.URGENT, **_neutral_expensive()))
    assert result.recommendation is Recommendation.WAIT
    assert result.buying_window is BuyingWindow.BUY_IN_ORDINARY_SALE
    assert RuleId.WAIT_ORDINARY_SALE_SOON in result.triggered_rule_ids
    assert result.expected_saving == Decimal("2500.00")
    assert result.expected_saving_percentage == Decimal("5.00")
    assert "urgent" in " ".join(result.reasons).lower()


def test_patient_waits_for_worthwhile_major_sale() -> None:
    result = engine().recommend(payload(urgency=Urgency.PATIENT, **_neutral_expensive()))
    assert result.recommendation is Recommendation.WAIT
    assert result.buying_window is BuyingWindow.WAIT_FOR_MAJOR_SALE
    assert RuleId.WAIT_MAJOR_SALE_WORTHWHILE in result.triggered_rule_ids
    assert result.expected_saving == Decimal("7000.00")
    assert result.expected_saving_percentage == Decimal("14.00")


def test_urgent_buy_now_when_price_is_already_strong() -> None:
    result = engine().recommend(
        payload(
            urgency=Urgency.URGENT,
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("10.00", unit="percentile"),
            historical_low=calculated("98.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("150.00", window_days=90),
            trend_direction=TrendDirection.FALLING,
            ordinary_opportunity=opportunity(),
            major_opportunity=opportunity(
                sale_type="MAJOR",
                days_until_start=40,
                expected_price=Decimal("80.00"),
                expected_saving=Decimal("20.00"),
                expected_saving_percentage=Decimal("20.00"),
            ),
        )
    )
    assert result.recommendation is Recommendation.BUY_NOW
    assert result.buying_window is BuyingWindow.BUY_NOW


def test_patient_does_not_wait_when_major_saving_is_not_worthwhile() -> None:
    result = engine().recommend(
        payload(
            urgency=Urgency.PATIENT,
            current_effective_price=Decimal("50000.00"),
            historical_percentile=calculated("45.00", unit="percentile"),
            historical_low=calculated("40000.00"),
            average_30d=calculated("49800.00", window_days=30),
            average_90d=calculated("50100.00", window_days=90),
            ordinary_opportunity=opportunity(
                expected_saving=Decimal("2400.00"),
                expected_saving_percentage=Decimal("4.80"),
            ),
            major_opportunity=opportunity(
                sale_type="MAJOR",
                days_until_start=40,
                expected_price=Decimal("49000.00"),
                expected_saving=Decimal("1000.00"),
                expected_saving_percentage=Decimal("2.00"),
            ),
        )
    )
    assert result.buying_window is not BuyingWindow.WAIT_FOR_MAJOR_SALE
    assert RuleId.WAIT_MAJOR_SALE_WORTHWHILE not in result.triggered_rule_ids


def test_insufficient_sale_opportunity_does_not_guess() -> None:
    result = engine().recommend(
        payload(
            urgency=Urgency.URGENT,
            current_effective_price=Decimal("50000.00"),
            historical_percentile=calculated("45.00", unit="percentile"),
            historical_low=calculated("40000.00"),
            average_30d=calculated("49800.00", window_days=30),
            average_90d=calculated("50100.00", window_days=90),
            ordinary_opportunity=opportunity(status="insufficient_history", expected_price=None),
            major_opportunity=None,
        )
    )
    assert result.recommendation is Recommendation.BUY_NOW
    assert result.buying_window is BuyingWindow.BUY_NOW


def test_predicted_saving_percentage_is_additive() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("200.00"),
            historical_percentile=calculated("45.00", unit="percentile"),
            historical_low=calculated("140.00"),
            average_30d=calculated("195.00", window_days=30),
            average_90d=calculated("198.00", window_days=90),
            prediction=prediction(price="150.00", confidence=0.82),
        )
    )
    assert result.recommendation is Recommendation.WAIT
    assert result.expected_saving == Decimal("50.00")
    assert result.expected_saving_percentage == Decimal("25.00")
    assert result.expected_saving_value_kind is ValueKind.CALCULATED
    assert result.buying_window is BuyingWindow.WAIT


def test_near_historical_low_is_buy_now_even_when_a_future_sale_exists() -> None:
    result = engine().recommend(
        payload(
            current_effective_price=Decimal("100.00"),
            historical_percentile=calculated("8.00", unit="percentile"),
            historical_low=calculated("99.00"),
            average_30d=calculated("140.00", window_days=30),
            average_90d=calculated("150.00", window_days=90),
            upcoming_events=(upcoming(days=12),),
        )
    )
    assert result.recommendation is Recommendation.BUY_NOW
    assert RuleId.WAIT_UPCOMING_SALE not in result.triggered_rule_ids
    assert result.expected_saving is None
