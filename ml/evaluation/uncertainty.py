"""Validation-residual uncertainty for predicted sale prices.

Lower/upper bounds are the prediction plus the configured residual percentiles from the
chronological validation split (default 10th and 90th). Confidence is derived from that
split's empirical coverage, relative RMSE, and the fraction of features that were actually
available at prediction time. Values are not arbitrary constants.
"""

from __future__ import annotations

import math

import numpy as np

from ml.config import MLConfig
from ml.types import UncertaintyModel

UNCERTAINTY_METHOD = (
    "validation_residual_percentiles: predicted + P{lower}/P{upper} of (actual - predicted) "
    "on the chronological validation split; confidence = clip(coverage * feature_completeness "
    "/ (1 + relative_rmse), 0, 1)"
)


def fit_uncertainty(
    actual: np.ndarray,
    predicted: np.ndarray,
    config: MLConfig,
) -> UncertaintyModel:
    residuals = actual - predicted
    lower = float(np.percentile(residuals, config.residual_lower_percentile))
    upper = float(np.percentile(residuals, config.residual_upper_percentile))
    interval_low = predicted + lower
    interval_high = predicted + upper
    inside = (actual >= interval_low) & (actual <= interval_high)
    coverage = float(np.mean(inside)) if actual.size else 0.0
    errors = actual - predicted
    rmse = float(math.sqrt(float(np.mean(errors**2)))) if actual.size else 0.0
    mae = float(np.mean(np.abs(errors))) if actual.size else 0.0
    mean_target = float(np.mean(actual)) if actual.size else 0.0
    return UncertaintyModel(
        method=UNCERTAINTY_METHOD.format(
            lower=int(config.residual_lower_percentile),
            upper=int(config.residual_upper_percentile),
        ),
        residual_lower_percentile=config.residual_lower_percentile,
        residual_upper_percentile=config.residual_upper_percentile,
        residual_p_lower=lower,
        residual_p_upper=upper,
        validation_coverage=coverage,
        validation_rmse=rmse,
        validation_mae=mae,
        validation_mean_target=mean_target,
    )


def interval_and_confidence(
    predicted: float,
    uncertainty: UncertaintyModel,
    *,
    feature_completeness: float,
) -> tuple[float, float, float]:
    lower = max(0.0, predicted + uncertainty.residual_p_lower)
    upper = max(lower, predicted + uncertainty.residual_p_upper)
    relative_rmse = 0.0
    if uncertainty.validation_mean_target > 0:
        relative_rmse = uncertainty.validation_rmse / uncertainty.validation_mean_target
    completeness = min(1.0, max(0.0, feature_completeness))
    coverage = min(1.0, max(0.0, uncertainty.validation_coverage))
    confidence = coverage * completeness / (1.0 + relative_rmse)
    confidence = min(1.0, max(0.0, confidence))
    return lower, upper, confidence
