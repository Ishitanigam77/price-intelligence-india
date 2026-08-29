"""MAE and RMSE for sale-price predictions. Never invents a score when a split is empty."""

from __future__ import annotations

import math

import numpy as np

from ml.enums import SplitName
from ml.types import EvaluationMetrics


def mean_absolute_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    if actual.size == 0:
        raise ValueError("MAE is undefined for an empty split.")
    return float(np.mean(np.abs(actual - predicted)))


def root_mean_squared_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    if actual.size == 0:
        raise ValueError("RMSE is undefined for an empty split.")
    return float(math.sqrt(float(np.mean((actual - predicted) ** 2))))


def evaluate_split(
    actual: np.ndarray,
    predicted: np.ndarray,
    *,
    split: SplitName,
) -> EvaluationMetrics:
    return EvaluationMetrics(
        mae=mean_absolute_error(actual, predicted),
        rmse=root_mean_squared_error(actual, predicted),
        n=int(actual.size),
        split=split,
    )
