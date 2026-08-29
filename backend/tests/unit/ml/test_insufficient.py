"""INSUFFICIENT_DATA when legitimate history cannot support training or inference."""

from datetime import timedelta
from pathlib import Path

from ml.enums import InsufficientDataReason, PredictionStatus
from ml.inference.predict import predict
from ml.training.train import train, train_from_examples
from tests.unit.ml.helpers import ANCHOR, engineer, event_record, ml_config, observation, seed_ids


def test_train_with_no_points_is_insufficient() -> None:
    result = train([], [], config=ml_config(), engineer=engineer())
    assert result.status is PredictionStatus.INSUFFICIENT_DATA
    assert result.insufficient is not None
    assert result.insufficient.code is InsufficientDataReason.NO_LABELED_EXAMPLES
    assert result.metadata is None
    assert result.training_data_size == 0


def test_train_with_sale_but_no_pre_sale_history_is_insufficient() -> None:
    sale = event_record(start_date=ANCHOR + timedelta(days=2), end_date=ANCHOR + timedelta(days=5))
    during = observation(
        displayed_price="8.00",
        effective_price="8.00",
        observed_at=sale.start_date + timedelta(hours=12),
    )
    result = train([during], [sale], config=ml_config(), engineer=engineer())
    assert result.status is PredictionStatus.INSUFFICIENT_DATA
    assert result.insufficient is not None
    assert result.insufficient.code is InsufficientDataReason.NO_LABELED_EXAMPLES


def test_train_does_not_write_artifact_when_insufficient(tmp_path: Path) -> None:
    result = train([], [], config=ml_config(), engineer=engineer(), artifact_root=tmp_path)
    assert result.status is PredictionStatus.INSUFFICIENT_DATA
    assert list(tmp_path.iterdir()) == []


def test_too_few_chronological_rows_is_insufficient() -> None:
    sale = event_record(start_date=ANCHOR + timedelta(days=5), end_date=ANCHOR + timedelta(days=8))
    listing_id, variant_id = seed_ids()
    points = [
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="20.00",
            effective_price="20.00",
            observed_at=ANCHOR,
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="15.00",
            effective_price="15.00",
            observed_at=sale.start_date + timedelta(days=1),
        ),
    ]
    result = train(
        points,
        [sale],
        config=ml_config(min_train_rows=20, min_validation_rows=6, min_test_rows=6),
        engineer=engineer(),
    )
    assert result.status is PredictionStatus.INSUFFICIENT_DATA
    assert result.insufficient is not None
    assert result.insufficient.code in {
        InsufficientDataReason.BELOW_MINIMUM_TRAIN_ROWS,
        InsufficientDataReason.BELOW_MINIMUM_VALIDATION_ROWS,
        InsufficientDataReason.BELOW_MINIMUM_TEST_ROWS,
        InsufficientDataReason.NO_LABELED_EXAMPLES,
    }


def test_empty_example_list_from_examples_is_insufficient() -> None:
    result = train_from_examples([], config=ml_config())
    assert result.status is PredictionStatus.INSUFFICIENT_DATA


def test_inference_without_model_is_insufficient(tmp_path: Path) -> None:
    point = observation(displayed_price="20.00", effective_price="20.00", observed_at=ANCHOR)
    prediction = predict(
        [point],
        [],
        as_of=ANCHOR + timedelta(days=1),
        artifact_root=tmp_path,
        engineer=engineer(),
    )
    assert prediction.status is PredictionStatus.INSUFFICIENT_DATA
    assert prediction.predicted_price is None
    assert prediction.lower_bound is None
    assert prediction.upper_bound is None
    assert prediction.confidence is None
    assert prediction.insufficient is not None
    assert prediction.insufficient.code is InsufficientDataReason.NO_TRAINED_MODEL
    assert prediction.value_kind.value == "PREDICTED"
    assert prediction.is_prediction is True
