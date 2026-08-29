"""Inference: load a versioned model and emit a clearly labeled prediction.

Never returns a bare price. INSUFFICIENT_DATA is used when there is no trained artifact,
the cutoff history cannot support features, or the requested version is missing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.observability.logging import get_logger
from app.pricing.money import quantize_money
from app.sales.models import SaleEventRecord, SalePricePoint
from ml.config import FEATURE_VERSION, PREDICTION_DISCLAIMER, MLConfig, get_ml_config
from ml.enums import InsufficientDataReason, PredictionStatus
from ml.evaluation.uncertainty import interval_and_confidence
from ml.features.engineering import FeatureEngineer, feature_completeness
from ml.inference.registry import LoadedModel, load_model
from ml.types import InsufficientData, SalePricePrediction

logger = get_logger(__name__)


def _insufficient(
    *,
    code: InsufficientDataReason,
    reason: str,
    as_of: datetime,
    model: LoadedModel | None = None,
    product_id=None,
    product_variant_id=None,
    retailer_id=None,
    seller_id=None,
) -> SalePricePrediction:
    metadata = model.metadata if model is not None else None
    return SalePricePrediction(
        status=PredictionStatus.INSUFFICIENT_DATA,
        disclaimer=PREDICTION_DISCLAIMER,
        as_of=as_of,
        model_version=metadata.model_version if metadata else None,
        training_data_size=metadata.training_data_size if metadata else None,
        feature_version=metadata.feature_version if metadata else FEATURE_VERSION,
        product_id=product_id,
        product_variant_id=product_variant_id,
        retailer_id=retailer_id,
        seller_id=seller_id,
        insufficient=InsufficientData(code=code, reason=reason),
        uncertainty_method=metadata.uncertainty.method if metadata else None,
    )


def predict_listing(
    points: Sequence[SalePricePoint],
    events: Sequence[SaleEventRecord],
    *,
    as_of: datetime,
    model: LoadedModel,
    engineer: FeatureEngineer | None = None,
) -> SalePricePrediction:
    """Predict the effective sale price for one listing series at `as_of`."""
    feature_engineer = engineer if engineer is not None else FeatureEngineer()
    vector = feature_engineer.build(points, events, as_of=as_of)
    first = points[0].observation if points else None
    if vector is None:
        return _insufficient(
            code=InsufficientDataReason.NO_CURRENT_PRICE,
            reason=(
                "No qualifying verified observation exists strictly before the prediction "
                "timestamp, so current price and historical aggregates cannot be built. "
                "A price is not invented."
            ),
            as_of=as_of,
            model=model,
            product_id=first.product_id if first else None,
            product_variant_id=first.product_variant_id if first else None,
            retailer_id=first.retailer_id if first else None,
            seller_id=first.seller_id if first else None,
        )
    if vector.feature_version != model.metadata.feature_version:
        return _insufficient(
            code=InsufficientDataReason.FEATURE_VERSION_MISMATCH,
            reason=(
                f"Feature version {vector.feature_version} does not match model "
                f"{model.metadata.feature_version}."
            ),
            as_of=as_of,
            model=model,
            product_id=vector.product_id,
            product_variant_id=vector.product_variant_id,
            retailer_id=vector.retailer_id,
            seller_id=vector.seller_id,
        )
    matrix = model.preprocessor.transform_features([vector])
    predicted = model.predict_matrix(matrix)[0]
    predicted = max(0.0, float(predicted))
    lower, upper, confidence = interval_and_confidence(
        predicted,
        model.metadata.uncertainty,
        feature_completeness=feature_completeness(vector),
    )
    logger.info(
        "ml.inference.predicted",
        extra={
            "model_version": model.metadata.model_version,
            "product_variant_id": str(vector.product_variant_id),
            "as_of": as_of.isoformat(),
            "is_prediction": True,
        },
    )
    return SalePricePrediction(
        status=PredictionStatus.PREDICTED,
        predicted_price=quantize_money(Decimal(str(predicted))),
        lower_bound=quantize_money(Decimal(str(lower))),
        upper_bound=quantize_money(Decimal(str(upper))),
        confidence=confidence,
        model_version=model.metadata.model_version,
        training_data_size=model.metadata.training_data_size,
        as_of=as_of,
        product_id=vector.product_id,
        product_variant_id=vector.product_variant_id,
        retailer_id=vector.retailer_id,
        seller_id=vector.seller_id,
        feature_version=vector.feature_version,
        uncertainty_method=model.metadata.uncertainty.method,
    )


def predict(
    points: Sequence[SalePricePoint],
    events: Sequence[SaleEventRecord],
    *,
    as_of: datetime,
    artifact_root: Path | None = None,
    model_version: str | None = None,
    config: MLConfig | None = None,
    engineer: FeatureEngineer | None = None,
) -> SalePricePrediction:
    cfg = config if config is not None else get_ml_config()
    root = artifact_root if artifact_root is not None else cfg.artifact_dir
    model = load_model(root, model_version=model_version)
    first = points[0].observation if points else None
    if model is None:
        code = (
            InsufficientDataReason.MODEL_NOT_FOUND
            if model_version
            else InsufficientDataReason.NO_TRAINED_MODEL
        )
        reason = (
            f"No trained sale-price model version {model_version!r} was found."
            if model_version
            else (
                "No trained sale-price model is available. The pipeline does not fabricate "
                "historical prices in order to train one."
            )
        )
        return _insufficient(
            code=code,
            reason=reason,
            as_of=as_of,
            product_id=first.product_id if first else None,
            product_variant_id=first.product_variant_id if first else None,
            retailer_id=first.retailer_id if first else None,
            seller_id=first.seller_id if first else None,
        )
    return predict_listing(points, events, as_of=as_of, model=model, engineer=engineer)
