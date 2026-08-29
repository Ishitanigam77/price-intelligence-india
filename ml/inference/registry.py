"""Load a versioned booster and produce labeled sale-price predictions."""

from __future__ import annotations

from pathlib import Path

import xgboost as xgb

from ml.models.artifact import (
    MODEL_FILE,
    latest_version,
    read_metadata,
    read_preprocessor,
    version_dir,
)
from ml.preprocessing.encode import FeaturePreprocessor
from ml.types import ModelMetadata


class LoadedModel:
    """A booster plus the preprocessor and metadata it was trained with."""

    def __init__(
        self,
        *,
        booster: xgb.Booster,
        preprocessor: FeaturePreprocessor,
        metadata: ModelMetadata,
        directory: Path,
    ) -> None:
        self.booster = booster
        self.preprocessor = preprocessor
        self.metadata = metadata
        self.directory = directory

    def predict_matrix(self, features) -> list[float]:
        matrix = xgb.DMatrix(features, feature_names=list(self.preprocessor.feature_names))
        raw = self.booster.predict(matrix)
        return [float(value) for value in raw]


def load_model(
    root: Path,
    *,
    model_version: str | None = None,
) -> LoadedModel | None:
    version = model_version if model_version else latest_version(root)
    if not version:
        return None
    directory = version_dir(root, version)
    model_path = directory / MODEL_FILE
    if not model_path.is_file():
        return None
    booster = xgb.Booster()
    booster.load_model(str(model_path))
    return LoadedModel(
        booster=booster,
        preprocessor=read_preprocessor(directory),
        metadata=read_metadata(directory),
        directory=directory,
    )
