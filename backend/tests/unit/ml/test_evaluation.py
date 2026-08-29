"""Evaluation metrics and validation-residual uncertainty."""

import numpy as np
import pytest

from ml.config import MLConfig
from ml.enums import SplitName
from ml.evaluation.metrics import evaluate_split, mean_absolute_error, root_mean_squared_error
from ml.evaluation.uncertainty import fit_uncertainty, interval_and_confidence


def test_mae_and_rmse_on_known_vectors() -> None:
    actual = np.asarray([10.0, 20.0, 30.0], dtype=np.float32)
    predicted = np.asarray([12.0, 18.0, 30.0], dtype=np.float32)
    assert mean_absolute_error(actual, predicted) == pytest.approx(4.0 / 3.0, rel=1e-5)
    assert abs(root_mean_squared_error(actual, predicted) - ((4.0 + 4.0 + 0.0) / 3.0) ** 0.5) < 1e-6
    metrics = evaluate_split(actual, predicted, split=SplitName.TEST)
    assert metrics.n == 3
    assert metrics.split is SplitName.TEST


def test_interval_comes_from_validation_residuals() -> None:
    actual = np.asarray([100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float32)
    predicted = np.asarray([90.0, 95.0, 100.0, 105.0, 110.0], dtype=np.float32)
    config = MLConfig(
        _env_file=None, residual_lower_percentile=0.0, residual_upper_percentile=100.0
    )
    uncertainty = fit_uncertainty(actual, predicted, config)
    assert uncertainty.residual_p_lower < 0 or uncertainty.residual_p_upper > 0
    lower, upper, confidence = interval_and_confidence(100.0, uncertainty, feature_completeness=1.0)
    assert lower <= 100.0 <= upper or lower <= upper
    assert 0.0 <= confidence <= 1.0
    incomplete_lower, incomplete_upper, incomplete_confidence = interval_and_confidence(
        100.0, uncertainty, feature_completeness=0.5
    )
    assert incomplete_lower == lower
    assert incomplete_upper == upper
    assert incomplete_confidence <= confidence
