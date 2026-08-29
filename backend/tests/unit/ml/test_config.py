"""MLConfig environment parsing."""

from ml.config import MLConfig


def test_ml_config_defaults() -> None:
    config = MLConfig(_env_file=None)
    assert config.min_train_rows >= 1
    assert config.min_validation_rows >= 1
    assert config.min_test_rows >= 1
    assert 0 < config.train_fraction < 1
    assert config.residual_lower_percentile < config.residual_upper_percentile
    assert config.artifact_dir.name == "artifacts"


def test_ml_config_artifact_path_override(tmp_path) -> None:
    config = MLConfig(_env_file=None, model_artifact_path=str(tmp_path))
    assert config.artifact_dir == tmp_path
