"""Retailer-agnostic contracts for sale-price features, predictions, and model metadata.

Predicted values are labeled PREDICTED and never mixed with observed or calculated prices.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.pricing.enums import ValueKind
from app.pricing.money import quantize_money
from ml.config import FEATURE_VERSION, MODEL_TYPE, PREDICTION_DISCLAIMER
from ml.enums import InsufficientDataReason, PredictionStatus, SplitName


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class InsufficientData(_FrozenModel):
    code: InsufficientDataReason
    reason: str


class FeatureVector(_FrozenModel):
    """Leakage-safe features at a single prediction timestamp.

    Missing numeric/categorical entries are explicit `None` — never zero-filled, guessed, or
    replaced with the target.
    """

    feature_version: str = FEATURE_VERSION
    as_of: datetime
    product_id: uuid.UUID
    product_variant_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_product_id: uuid.UUID
    seller_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    numeric: dict[str, float | None]
    categorical: dict[str, str | None]
    available: dict[str, bool]

    @field_validator("as_of")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Prediction timestamps must be timezone-aware.")
        return value


class LabeledExample(_FrozenModel):
    """One training row: features known at `as_of` and the later observed sale price."""

    features: FeatureVector
    target_sale_price: Decimal
    target_event_id: uuid.UUID
    target_observation_count: int = Field(ge=1)
    listing_key: tuple[str, str]

    @field_validator("target_sale_price")
    @classmethod
    def _quantize_target(cls, value: Decimal) -> Decimal:
        return quantize_money(value)


class SplitAssignment(_FrozenModel):
    train: tuple[LabeledExample, ...]
    validation: tuple[LabeledExample, ...]
    test: tuple[LabeledExample, ...]
    train_as_of_start: datetime | None = None
    train_as_of_end: datetime | None = None
    validation_as_of_start: datetime | None = None
    validation_as_of_end: datetime | None = None
    test_as_of_start: datetime | None = None
    test_as_of_end: datetime | None = None

    @property
    def by_name(self) -> dict[SplitName, tuple[LabeledExample, ...]]:
        return {
            SplitName.TRAIN: self.train,
            SplitName.VALIDATION: self.validation,
            SplitName.TEST: self.test,
        }


class EvaluationMetrics(_FrozenModel):
    mae: float
    rmse: float
    n: int = Field(ge=0)
    split: SplitName


class UncertaintyModel(_FrozenModel):
    """Validation-residual interval used at inference. Not an arbitrary confidence score."""

    method: str
    residual_lower_percentile: float
    residual_upper_percentile: float
    residual_p_lower: float
    residual_p_upper: float
    validation_coverage: float
    validation_rmse: float
    validation_mae: float
    validation_mean_target: float


class ModelMetadata(_FrozenModel):
    model_version: str
    model_type: str = MODEL_TYPE
    feature_version: str = FEATURE_VERSION
    training_timestamp: datetime
    training_data_size: int = Field(ge=0)
    train_size: int = Field(ge=0)
    validation_size: int = Field(ge=0)
    test_size: int = Field(ge=0)
    train_as_of_start: datetime | None = None
    train_as_of_end: datetime | None = None
    validation_as_of_start: datetime | None = None
    validation_as_of_end: datetime | None = None
    test_as_of_start: datetime | None = None
    test_as_of_end: datetime | None = None
    mae: float
    rmse: float
    validation_mae: float
    validation_rmse: float
    feature_names: tuple[str, ...]
    uncertainty: UncertaintyModel
    leakage_prevention: str
    split_strategy: str = "chronological_by_prediction_timestamp"
    notes: str = PREDICTION_DISCLAIMER


class SalePricePrediction(_FrozenModel):
    """Inference output. `predicted_price` is None when status is INSUFFICIENT_DATA."""

    value_kind: Literal[ValueKind.PREDICTED] = ValueKind.PREDICTED
    is_prediction: Literal[True] = True
    disclaimer: str = PREDICTION_DISCLAIMER
    status: PredictionStatus
    predicted_price: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model_version: str | None = None
    training_data_size: int | None = Field(default=None, ge=0)
    currency: str = "INR"
    as_of: datetime
    product_id: uuid.UUID | None = None
    product_variant_id: uuid.UUID | None = None
    retailer_id: uuid.UUID | None = None
    seller_id: uuid.UUID | None = None
    feature_version: str | None = None
    insufficient: InsufficientData | None = None
    uncertainty_method: str | None = None

    @field_validator("predicted_price", "lower_bound", "upper_bound")
    @classmethod
    def _quantize_optional_money(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return quantize_money(value)


class TrainingResult(_FrozenModel):
    status: PredictionStatus
    metadata: ModelMetadata | None = None
    metrics: tuple[EvaluationMetrics, ...] = ()
    artifact_dir: str | None = None
    insufficient: InsufficientData | None = None
    training_data_size: int = Field(ge=0)
