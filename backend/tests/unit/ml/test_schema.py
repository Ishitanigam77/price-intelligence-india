"""Prediction schema: predicted vs insufficient payloads stay distinct."""

from datetime import timedelta

from app.pricing.enums import ValueKind
from ml.config import PREDICTION_DISCLAIMER
from ml.enums import InsufficientDataReason, PredictionStatus
from ml.types import InsufficientData, SalePricePrediction
from tests.unit.ml.helpers import ANCHOR, PRODUCT_ID


def test_predicted_schema_requires_prediction_label() -> None:
    payload = SalePricePrediction(
        status=PredictionStatus.PREDICTED,
        predicted_price="99.50",
        lower_bound="80.00",
        upper_bound="120.00",
        confidence=0.4,
        model_version="sale-price-xgb-features-v1-test",
        training_data_size=80,
        as_of=ANCHOR + timedelta(days=1),
        product_id=PRODUCT_ID,
    )
    dumped = payload.model_dump()
    assert dumped["value_kind"] is ValueKind.PREDICTED
    assert dumped["is_prediction"] is True
    assert dumped["disclaimer"] == PREDICTION_DISCLAIMER
    assert dumped["status"] is PredictionStatus.PREDICTED
    assert dumped["predicted_price"] is not None
    assert "guaranteed" in dumped["disclaimer"].lower()


def test_insufficient_schema_omits_invented_prices() -> None:
    payload = SalePricePrediction(
        status=PredictionStatus.INSUFFICIENT_DATA,
        as_of=ANCHOR,
        insufficient=InsufficientData(
            code=InsufficientDataReason.NO_TRAINED_MODEL,
            reason="No trained sale-price model is available.",
        ),
    )
    assert payload.predicted_price is None
    assert payload.lower_bound is None
    assert payload.upper_bound is None
    assert payload.confidence is None
    assert payload.status is PredictionStatus.INSUFFICIENT_DATA
    assert payload.value_kind is ValueKind.PREDICTED
    assert payload.is_prediction is True
