"""Inference output schema and loading a trained model version."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.pricing.enums import ValueKind
from ml.enums import PredictionStatus
from ml.inference.predict import predict
from ml.inference.registry import load_model
from ml.training.train import train
from tests.unit.ml.helpers import ANCHOR, engineer, fixture_catalog, ml_config


def _train(tmp_path: Path):
    points, events = fixture_catalog()
    result = train(
        points,
        events,
        config=ml_config(
            min_train_rows=20,
            min_validation_rows=6,
            min_test_rows=6,
            num_boost_round=30,
            early_stopping_rounds=8,
        ),
        engineer=engineer(),
        artifact_root=tmp_path,
        trained_at=datetime(2026, 8, 29, 8, 0, tzinfo=UTC),
    )
    assert result.status is PredictionStatus.TRAINED
    return points, events, result


def test_inference_returns_required_prediction_fields(tmp_path: Path) -> None:
    points, events, result = _train(tmp_path)
    as_of = max(event.start_date for event in events) + timedelta(days=1)
    prediction = predict(
        points,
        events,
        as_of=as_of,
        artifact_root=tmp_path,
        engineer=engineer(),
    )
    assert prediction.status is PredictionStatus.PREDICTED
    assert prediction.value_kind is ValueKind.PREDICTED
    assert prediction.is_prediction is True
    assert "not a guaranteed" in prediction.disclaimer.lower()
    assert prediction.predicted_price is not None
    assert prediction.lower_bound is not None
    assert prediction.upper_bound is not None
    assert prediction.lower_bound <= prediction.upper_bound
    assert prediction.confidence is not None
    assert 0.0 <= prediction.confidence <= 1.0
    assert prediction.model_version == result.metadata.model_version
    assert prediction.training_data_size == result.training_data_size
    assert prediction.insufficient is None
    assert prediction.uncertainty_method is not None


def test_inference_loads_specified_model_version(tmp_path: Path) -> None:
    _train(tmp_path)
    loaded = load_model(tmp_path)
    assert loaded is not None
    missing = load_model(tmp_path, model_version="sale-price-xgb-features-v1-missing")
    assert missing is None


def test_inference_without_pre_as_of_history_is_insufficient(tmp_path: Path) -> None:
    points, events, _result = _train(tmp_path)
    prediction = predict(
        points,
        events,
        as_of=ANCHOR,
        artifact_root=tmp_path,
        engineer=engineer(),
    )
    assert prediction.status is PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_price is None
