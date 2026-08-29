"""Configurable thresholds for sale-price model training, evaluation, and artifacts.

Sourced from `ML_*` environment variables. No secrets are required.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

FEATURE_VERSION = "features-v1"
MODEL_TYPE = "xgboost_regressor"

PREDICTION_DISCLAIMER = (
    "This is a model prediction of a possible effective sale price, not a guaranteed, "
    "observed, or calculated price. It must not be treated as a live retailer offer."
)

LEAKAGE_PREVENTION_SUMMARY = (
    "Features for a prediction timestamp T use only observations with observed_at < T and "
    "created_at < T. Historical averages, extrema, and volatility are computed on that "
    "cutoff set. Previous-sale features use only sale windows that ended before T. "
    "Inferred (observed-price) sale events are never treated as known upcoming events. "
    "The target effective sale price and any in-window observations of the target event "
    "are excluded from inputs. Splits are chronological by prediction timestamp."
)


class MLConfig(BaseSettings):
    """Environment-driven ML configuration, independent of FastAPI settings."""

    model_config = SettingsConfigDict(
        env_prefix="ML_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_artifact_path: str = ""
    min_train_rows: int = Field(default=20, ge=1, le=1_000_000)
    min_validation_rows: int = Field(default=6, ge=1, le=1_000_000)
    min_test_rows: int = Field(default=6, ge=1, le=1_000_000)
    min_target_observations: int = Field(default=1, ge=1, le=1000)
    train_fraction: float = Field(default=0.70, gt=0.0, lt=1.0)
    validation_fraction: float = Field(default=0.15, gt=0.0, lt=1.0)
    residual_lower_percentile: float = Field(default=10.0, ge=0.0, lt=50.0)
    residual_upper_percentile: float = Field(default=90.0, gt=50.0, le=100.0)
    num_boost_round: int = Field(default=80, ge=1, le=5000)
    early_stopping_rounds: int = Field(default=10, ge=1, le=1000)
    max_depth: int = Field(default=3, ge=1, le=16)
    learning_rate: float = Field(default=0.1, gt=0.0, le=1.0)
    subsample: float = Field(default=0.8, gt=0.0, le=1.0)
    colsample_bytree: float = Field(default=0.8, gt=0.0, le=1.0)
    nthread: int = Field(default=1, ge=1, le=64)

    @property
    def artifact_dir(self) -> Path:
        if self.model_artifact_path.strip():
            return Path(self.model_artifact_path).expanduser()
        return Path(__file__).resolve().parent / "models" / "artifacts"


@lru_cache
def get_ml_config() -> MLConfig:
    """Cached ML config. Tests that mutate env should call `cache_clear()`."""
    return MLConfig()
