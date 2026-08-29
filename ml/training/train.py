"""XGBoost training for effective sale-price prediction.

Trains only on leakage-safe, chronologically split labeled examples built from stored
observations and sale events. If any required split is too small, returns INSUFFICIENT_DATA
and writes no artifact. Historical prices are never fabricated to force a fit.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import xgboost as xgb

from app.observability.logging import get_logger
from app.sales.models import SaleEventRecord, SalePricePoint
from ml.config import (
    FEATURE_VERSION,
    LEAKAGE_PREVENTION_SUMMARY,
    MODEL_TYPE,
    MLConfig,
    get_ml_config,
)
from ml.enums import InsufficientDataReason, PredictionStatus, SplitName
from ml.evaluation.metrics import evaluate_split
from ml.evaluation.uncertainty import fit_uncertainty
from ml.features.engineering import FeatureEngineer
from ml.models.artifact import make_model_version, save_artifact
from ml.preprocessing.encode import FeaturePreprocessor
from ml.training.dataset import build_labeled_examples
from ml.training.split import chronological_split
from ml.types import (
    InsufficientData,
    LabeledExample,
    ModelMetadata,
    SplitAssignment,
    TrainingResult,
)

logger = get_logger(__name__)


def _xgb_params(config: MLConfig) -> dict[str, float | int | str]:
    return {
        "objective": "reg:squarederror",
        "max_depth": config.max_depth,
        "eta": config.learning_rate,
        "subsample": config.subsample,
        "colsample_bytree": config.colsample_bytree,
        "tree_method": "hist",
        "verbosity": 0,
        "nthread": config.nthread,
    }


def train_from_examples(
    examples: Sequence[LabeledExample],
    *,
    config: MLConfig | None = None,
    artifact_root: Path | None = None,
    trained_at: datetime | None = None,
) -> TrainingResult:
    cfg = config if config is not None else get_ml_config()
    split = chronological_split(examples, cfg)
    if isinstance(split, TrainingResult):
        logger.info(
            "ml.training.insufficient_data",
            extra={
                "code": split.insufficient.code.value if split.insufficient else None,
                "training_data_size": split.training_data_size,
            },
        )
        return split

    preprocessor = FeaturePreprocessor().fit(split.train)
    x_train, y_train = preprocessor.transform(split.train)
    x_val, y_val = preprocessor.transform(split.validation)
    x_test, y_test = preprocessor.transform(split.test)
    if x_train.size == 0:
        return TrainingResult(
            status=PredictionStatus.INSUFFICIENT_DATA,
            insufficient=InsufficientData(
                code=InsufficientDataReason.EMPTY_FEATURE_MATRIX,
                reason="The training feature matrix is empty after preprocessing.",
            ),
            training_data_size=len(examples),
        )

    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=list(preprocessor.feature_names))
    dval = xgb.DMatrix(x_val, label=y_val, feature_names=list(preprocessor.feature_names))
    dtest = xgb.DMatrix(x_test, label=y_test, feature_names=list(preprocessor.feature_names))
    booster = xgb.train(
        _xgb_params(cfg),
        dtrain,
        num_boost_round=cfg.num_boost_round,
        evals=[(dval, "validation")],
        early_stopping_rounds=cfg.early_stopping_rounds,
        verbose_eval=False,
    )
    val_pred = booster.predict(dval)
    test_pred = booster.predict(dtest)
    val_metrics = evaluate_split(
        y_val, np.asarray(val_pred, dtype=np.float32), split=SplitName.VALIDATION
    )
    test_metrics = evaluate_split(
        y_test, np.asarray(test_pred, dtype=np.float32), split=SplitName.TEST
    )
    uncertainty = fit_uncertainty(y_val, np.asarray(val_pred, dtype=np.float32), cfg)
    trained = trained_at if trained_at is not None else datetime.now(UTC)
    metadata = ModelMetadata(
        model_version=make_model_version(trained_at=trained),
        model_type=MODEL_TYPE,
        feature_version=FEATURE_VERSION,
        training_timestamp=trained,
        training_data_size=len(examples),
        train_size=len(split.train),
        validation_size=len(split.validation),
        test_size=len(split.test),
        train_as_of_start=split.train_as_of_start,
        train_as_of_end=split.train_as_of_end,
        validation_as_of_start=split.validation_as_of_start,
        validation_as_of_end=split.validation_as_of_end,
        test_as_of_start=split.test_as_of_start,
        test_as_of_end=split.test_as_of_end,
        mae=test_metrics.mae,
        rmse=test_metrics.rmse,
        validation_mae=val_metrics.mae,
        validation_rmse=val_metrics.rmse,
        feature_names=preprocessor.feature_names,
        uncertainty=uncertainty,
        leakage_prevention=LEAKAGE_PREVENTION_SUMMARY,
    )
    root = artifact_root if artifact_root is not None else cfg.artifact_dir
    directory = save_artifact(
        root=root, metadata=metadata, booster=booster, preprocessor=preprocessor
    )
    logger.info(
        "ml.training.completed",
        extra={
            "model_version": metadata.model_version,
            "training_data_size": metadata.training_data_size,
            "mae": metadata.mae,
            "rmse": metadata.rmse,
            "artifact_dir": str(directory),
        },
    )
    return TrainingResult(
        status=PredictionStatus.TRAINED,
        metadata=metadata,
        metrics=(val_metrics, test_metrics),
        artifact_dir=str(directory),
        training_data_size=len(examples),
    )


def train(
    points: Sequence[SalePricePoint],
    events: Sequence[SaleEventRecord],
    *,
    config: MLConfig | None = None,
    engineer: FeatureEngineer | None = None,
    artifact_root: Path | None = None,
    trained_at: datetime | None = None,
) -> TrainingResult:
    """Build examples from stored data and train. Does not fabricate missing history."""
    examples = build_labeled_examples(points, events, engineer=engineer, config=config)
    if not examples:
        result = TrainingResult(
            status=PredictionStatus.INSUFFICIENT_DATA,
            insufficient=InsufficientData(
                code=InsufficientDataReason.NO_LABELED_EXAMPLES,
                reason=(
                    "No labeled sale-price examples could be built from the supplied "
                    "observations and sale events. A listing needs qualifying pre-sale "
                    "history and at least one qualifying in-window sale observation. "
                    "Prices are not fabricated to enable training."
                ),
            ),
            training_data_size=0,
        )
        logger.info("ml.training.insufficient_data", extra={"code": result.insufficient.code.value})
        return result
    return train_from_examples(
        examples, config=config, artifact_root=artifact_root, trained_at=trained_at
    )


def require_split(result: SplitAssignment | TrainingResult) -> SplitAssignment:
    if isinstance(result, TrainingResult):
        raise ValueError("Expected a chronological split, received INSUFFICIENT_DATA.")
    return result
