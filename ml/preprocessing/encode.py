"""Train-only categorical encoding and numeric matrix assembly.

Encoders are fitted on the training split only. Unknown validation/test/inference categories
become missing (`NaN`) rather than a code learned from the future. Missing numerics stay NaN
so XGBoost can split on missingness; they are never filled with zeros or with the target.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ml.features.catalog import (
    CATEGORICAL_FEATURES,
    FEATURE_NAMES,
    NUMERIC_FEATURES,
    encoded_feature_name,
)
from ml.types import FeatureVector, LabeledExample


class FeaturePreprocessor:
    """Maps feature vectors to a float32 matrix aligned to `FEATURE_NAMES`."""

    def __init__(self) -> None:
        self.feature_names: tuple[str, ...] = FEATURE_NAMES
        self.categorical_maps: dict[str, dict[str, int]] = {
            name: {} for name in CATEGORICAL_FEATURES
        }
        self._fitted = False

    def fit(self, examples: Sequence[LabeledExample]) -> FeaturePreprocessor:
        maps: dict[str, dict[str, int]] = {name: {} for name in CATEGORICAL_FEATURES}
        for example in examples:
            for name in CATEGORICAL_FEATURES:
                raw = example.features.categorical.get(name)
                if raw is None:
                    continue
                bucket = maps[name]
                if raw not in bucket:
                    bucket[raw] = len(bucket)
        self.categorical_maps = maps
        self._fitted = True
        return self

    def transform_features(self, vectors: Sequence[FeatureVector]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("FeaturePreprocessor.transform_features requires fit().")
        rows: list[list[float]] = []
        for vector in vectors:
            row: list[float] = []
            for name in NUMERIC_FEATURES:
                value = vector.numeric.get(name)
                row.append(float(value) if value is not None else float("nan"))
            for name in CATEGORICAL_FEATURES:
                raw = vector.categorical.get(name)
                code = self.categorical_maps[name].get(raw) if raw is not None else None
                row.append(float(code) if code is not None else float("nan"))
            rows.append(row)
        if not rows:
            return np.empty((0, len(self.feature_names)), dtype=np.float32)
        return np.asarray(rows, dtype=np.float32)

    def transform(self, examples: Sequence[LabeledExample]) -> tuple[np.ndarray, np.ndarray]:
        features = self.transform_features([example.features for example in examples])
        targets = np.asarray(
            [float(example.target_sale_price) for example in examples], dtype=np.float32
        )
        return features, targets

    def to_state(self) -> dict[str, object]:
        return {
            "feature_names": list(self.feature_names),
            "categorical_maps": self.categorical_maps,
            "fitted": self._fitted,
        }

    @classmethod
    def from_state(cls, state: dict[str, object]) -> FeaturePreprocessor:
        preprocessor = cls()
        names = state.get("feature_names")
        if isinstance(names, list):
            preprocessor.feature_names = tuple(str(item) for item in names)
        raw_maps = state.get("categorical_maps")
        if isinstance(raw_maps, dict):
            preprocessor.categorical_maps = {
                str(name): {str(key): int(value) for key, value in mapping.items()}
                for name, mapping in raw_maps.items()
                if isinstance(mapping, dict)
            }
        preprocessor._fitted = bool(state.get("fitted", True))
        return preprocessor


def matrix_contains_target(features: np.ndarray, targets: np.ndarray) -> bool:
    """Whether any feature column is identical to the target vector (leakage smoke test)."""
    if features.size == 0 or targets.size == 0:
        return False
    for index in range(features.shape[1]):
        column = features[:, index]
        if np.allclose(column, targets, equal_nan=False):
            return True
    return False


def encoded_columns() -> tuple[str, ...]:
    return tuple(encoded_feature_name(name) for name in CATEGORICAL_FEATURES)
