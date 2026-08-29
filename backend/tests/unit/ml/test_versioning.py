"""Model versioning and metadata persistence."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ml.enums import PredictionStatus
from ml.models.artifact import latest_version, make_model_version, read_metadata
from ml.training.train import train
from tests.unit.ml.helpers import engineer, fixture_catalog, ml_config


def test_model_version_includes_feature_version_and_timestamp() -> None:
    stamp = datetime(2026, 8, 29, 7, 1, tzinfo=UTC)
    version = make_model_version(trained_at=stamp)
    assert version == "sale-price-xgb-features-v1-20260829T070100Z"


def test_two_trained_models_are_versioned_separately(tmp_path: Path) -> None:
    points, events = fixture_catalog()
    config = ml_config(
        min_train_rows=20,
        min_validation_rows=6,
        min_test_rows=6,
        num_boost_round=20,
        early_stopping_rounds=5,
    )
    first = train(
        points,
        events,
        config=config,
        engineer=engineer(),
        artifact_root=tmp_path,
        trained_at=datetime(2026, 8, 29, 10, 0, tzinfo=UTC),
    )
    second = train(
        points,
        events,
        config=config,
        engineer=engineer(),
        artifact_root=tmp_path,
        trained_at=datetime(2026, 8, 29, 11, 0, tzinfo=UTC),
    )
    assert first.status is PredictionStatus.TRAINED
    assert second.status is PredictionStatus.TRAINED
    assert first.metadata is not None
    assert second.metadata is not None
    assert first.metadata.model_version != second.metadata.model_version
    assert latest_version(tmp_path) == second.metadata.model_version
    first_meta = read_metadata(tmp_path / first.metadata.model_version)
    second_meta = read_metadata(tmp_path / second.metadata.model_version)
    assert first_meta.training_timestamp == datetime(2026, 8, 29, 10, 0, tzinfo=UTC)
    assert second_meta.training_timestamp == datetime(2026, 8, 29, 11, 0, tzinfo=UTC)
    for meta in (first_meta, second_meta):
        assert meta.model_type == "xgboost_regressor"
        assert meta.feature_version == "features-v1"
        assert meta.training_data_size > 0
        assert meta.mae >= 0
        assert meta.rmse >= 0
        assert meta.train_as_of_start is not None
        assert meta.test_as_of_end is not None
        assert meta.uncertainty.method
        assert second_meta.training_timestamp - first_meta.training_timestamp == timedelta(hours=1)
