"""API schemas for sale-price predictions.

Predicted values are always labeled PREDICTED and never mixed with observed or calculated
prices. INSUFFICIENT_DATA is an explicit status, not a fabricated number.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.pricing.enums import ValueKind
from ml.config import PREDICTION_DISCLAIMER
from ml.enums import InsufficientDataReason, PredictionStatus
from ml.types import SalePricePrediction


class InsufficientDataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: InsufficientDataReason
    reason: str


class SalePricePredictionRead(BaseModel):
    """One listing-level predicted effective sale price."""

    model_config = ConfigDict(from_attributes=True)

    value_kind: Literal[ValueKind.PREDICTED] = ValueKind.PREDICTED
    is_prediction: Literal[True] = True
    disclaimer: str = PREDICTION_DISCLAIMER
    status: PredictionStatus
    predicted_price: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model_version: str | None = None
    training_data_size: int | None = None
    currency: str = "INR"
    as_of: datetime
    product_id: uuid.UUID | None = None
    product_variant_id: uuid.UUID | None = None
    retailer_id: uuid.UUID | None = None
    seller_id: uuid.UUID | None = None
    feature_version: str | None = None
    insufficient: InsufficientDataRead | None = None
    uncertainty_method: str | None = None


class ProductSalePricePredictionRead(BaseModel):
    """Predictions for every listing of a product. Variants are never merged."""

    product_id: uuid.UUID
    as_of: datetime
    value_kind: Literal[ValueKind.PREDICTED] = ValueKind.PREDICTED
    is_prediction: Literal[True] = True
    disclaimer: str = PREDICTION_DISCLAIMER
    status: PredictionStatus
    model_version: str | None = None
    training_data_size: int | None = None
    feature_version: str | None = None
    predictions: list[SalePricePredictionRead]
    insufficient: InsufficientDataRead | None = None


def prediction_read(prediction: SalePricePrediction) -> SalePricePredictionRead:
    insufficient = None
    if prediction.insufficient is not None:
        insufficient = InsufficientDataRead(
            code=prediction.insufficient.code, reason=prediction.insufficient.reason
        )
    return SalePricePredictionRead(
        value_kind=prediction.value_kind,
        is_prediction=True,
        disclaimer=prediction.disclaimer,
        status=prediction.status,
        predicted_price=prediction.predicted_price,
        lower_bound=prediction.lower_bound,
        upper_bound=prediction.upper_bound,
        confidence=prediction.confidence,
        model_version=prediction.model_version,
        training_data_size=prediction.training_data_size,
        currency=prediction.currency,
        as_of=prediction.as_of,
        product_id=prediction.product_id,
        product_variant_id=prediction.product_variant_id,
        retailer_id=prediction.retailer_id,
        seller_id=prediction.seller_id,
        feature_version=prediction.feature_version,
        insufficient=insufficient,
        uncertainty_method=prediction.uncertainty_method,
    )
