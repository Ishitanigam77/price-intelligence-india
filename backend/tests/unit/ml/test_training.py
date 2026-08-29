"""XGBoost training, evaluation metrics, and model metadata."""

from datetime import UTC, datetime
from pathlib import Path

from ml.enums import PredictionStatus, SplitName
from ml.models.artifact import latest_version, read_metadata
from ml.training.train import train
from tests.unit.ml.helpers import engineer, fixture_catalog, ml_config


def test_train_on_fixture_catalog_produces_metrics_and_artifact(tmp_path: Path) -> None:
    points, events = fixture_catalog()
    config = ml_config(
        min_train_rows=20,
        min_validation_rows=6,
        min_test_rows=6,
        num_boost_round=40,
        early_stopping_rounds=8,
        nthread=1,
    )
    trained_at = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    result = train(
        points,
        events,
        config=config,
        engineer=engineer(),
        artifact_root=tmp_path,
        trained_at=trained_at,
    )
    assert result.status is PredictionStatus.TRAINED
    assert result.metadata is not None
    assert result.training_data_size >= 20
    assert result.metadata.training_data_size == result.training_data_size
    assert result.metadata.model_type == "xgboost_regressor"
    assert result.metadata.feature_version == "features-v1"
    assert result.metadata.model_version.startswith("sale-price-xgb-features-v1-")
    assert result.metadata.mae >= 0.0
    assert result.metadata.rmse >= 0.0
    assert result.metadata.rmse >= result.metadata.mae  # RMSE is at least MAE
    assert result.metadata.train_as_of_end is not None
    assert result.metadata.validation_as_of_start is not None
    assert result.metadata.test_as_of_start is not None
    assert result.metadata.train_as_of_end <= result.metadata.validation_as_of_start
    assert result.metadata.validation_as_of_end <= result.metadata.test_as_of_start
    assert result.metadata.leakage_prevention
    splits = {item.split: item for item in result.metrics}
    assert SplitName.TEST in splits
    assert SplitName.VALIDATION in splits
    assert splits[SplitName.TEST].mae == result.metadata.mae
    assert splits[SplitName.TEST].rmse == result.metadata.rmse
    assert (tmp_path / "latest.json").is_file()
    assert latest_version(tmp_path) == result.metadata.model_version
    loaded = read_metadata(tmp_path / result.metadata.model_version)
    assert loaded.model_version == result.metadata.model_version
    assert loaded.training_timestamp == trained_at
