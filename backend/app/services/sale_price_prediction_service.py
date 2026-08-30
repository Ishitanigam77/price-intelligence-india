"""Sale-price prediction service: stored observations/events → ML inference.

Projects ORM rows into the same records Phase 9 uses, then calls the Phase 10 inference
layer. Does not train models, does not implement recommendations, and never presents a
prediction as an observed price.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.observability.names import (
    ML_PREDICTION_DURATION_MS,
    ML_PREDICTION_FAILURES,
    ML_PREDICTIONS,
)
from app.observability.telemetry import default_metric_tags
from app.pricing.freshness import utc_now
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.sale_event_repository import SaleEventRepository
from app.schemas.prediction import (
    InsufficientDataRead,
    ProductSalePricePredictionRead,
    prediction_read,
)
from app.services.sale_event_service import SaleEventService
from ml.config import FEATURE_VERSION, PREDICTION_DISCLAIMER, MLConfig, get_ml_config
from ml.enums import InsufficientDataReason, PredictionStatus
from ml.features.engineering import listing_group_key
from ml.inference.predict import predict_listing
from ml.inference.registry import load_model

logger = get_logger(__name__)


class SalePricePredictionService:
    """Orchestrates persistence → leakage-safe inference → API schema."""

    def __init__(
        self,
        session: Session,
        *,
        metrics_sink: MetricsSink | None = None,
        config: MLConfig | None = None,
        clock: Callable[[], datetime] | None = None,
        artifact_root: Path | None = None,
    ) -> None:
        self._session = session
        self._events = SaleEventRepository(session)
        self._products = ProductRepository(session)
        self._variants = ProductVariantRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now
        self._config = config if config is not None else get_ml_config()
        self._artifact_root = (
            artifact_root if artifact_root is not None else self._config.artifact_dir
        )

    def _record_prediction(
        self,
        *,
        started: float,
        status: str,
        model_version: str,
        failed: bool = False,
        error_type: str | None = None,
    ) -> None:
        duration_ms = (time.perf_counter() - started) * 1000
        tags = default_metric_tags(
            operation="predict",
            status=status,
            model_version=model_version or "none",
        )
        self._metrics.increment(ML_PREDICTIONS, tags=tags)
        self._metrics.observe(ML_PREDICTION_DURATION_MS, duration_ms, tags=tags)
        if failed:
            failure_tags = default_metric_tags(
                operation="predict",
                status="error",
                error_type=error_type or "prediction_failure",
            )
            self._metrics.increment(ML_PREDICTION_FAILURES, tags=failure_tags)

    def predict_product(
        self,
        product_id: uuid.UUID,
        *,
        variant_id: uuid.UUID | None = None,
        as_of: datetime | None = None,
        model_version: str | None = None,
    ) -> ProductSalePricePredictionRead:
        started = time.perf_counter()
        product = self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")

        at = as_of if as_of is not None else self._clock()
        variants = self._variants.list_for_product(product_id)
        if variant_id is not None:
            variants = [variant for variant in variants if variant.id == variant_id]
            if not variants:
                raise NotFoundError(
                    f"Product variant {variant_id} was not found on product {product_id}."
                )

        model = load_model(self._artifact_root, model_version=model_version)
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
                    "No trained sale-price model is available. Historical prices are not "
                    "fabricated to train one."
                )
            )
            logger.info(
                "ml.product_prediction.insufficient_data",
                extra={"product_id": str(product_id), "code": code.value},
            )
            self._record_prediction(
                started=started,
                status=PredictionStatus.INSUFFICIENT_DATA.value,
                model_version=model_version or "none",
            )
            return ProductSalePricePredictionRead(
                product_id=product_id,
                as_of=at,
                status=PredictionStatus.INSUFFICIENT_DATA,
                disclaimer=PREDICTION_DISCLAIMER,
                predictions=[],
                insufficient=InsufficientDataRead(code=code, reason=reason),
                feature_version=FEATURE_VERSION,
            )

        events = [
            SaleEventService._record(row)
            for row in self._events.list_applicable_to_product(
                brand_id=product.brand_id, category_id=product.category_id
            )
        ]
        snapshots = self._snapshots.history_for_product(product_id, variant_id=variant_id)
        grouped: dict[tuple, list] = defaultdict(list)
        allowed_variants = {variant.id for variant in variants}
        for snapshot in snapshots:
            listing = snapshot.retailer_product
            variant = listing.product_variant
            if variant.id not in allowed_variants:
                continue
            point = SaleEventService._point_from_snapshot(
                snapshot, product=product, variant=variant
            )
            grouped[listing_group_key(point)].append(point)

        predictions = [
            prediction_read(predict_listing(points, events, as_of=at, model=model))
            for points in grouped.values()
        ]
        predictions.sort(
            key=lambda item: (
                str(item.product_variant_id),
                str(item.retailer_id),
                str(item.seller_id),
            )
        )
        any_predicted = any(item.status is PredictionStatus.PREDICTED for item in predictions)
        status = PredictionStatus.PREDICTED if any_predicted else PredictionStatus.INSUFFICIENT_DATA
        insufficient = None
        if status is PredictionStatus.INSUFFICIENT_DATA:
            insufficient = InsufficientDataRead(
                code=InsufficientDataReason.NO_QUALIFYING_OBSERVATIONS,
                reason=(
                    "No listing of this product has qualifying verified observations "
                    "strictly before the prediction timestamp."
                ),
            )
        logger.info(
            "ml.product_prediction.completed",
            extra={
                "product_id": str(product_id),
                "status": status.value,
                "prediction_count": len(predictions),
                "model_version": model.metadata.model_version,
                "is_prediction": True,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        self._record_prediction(
            started=started,
            status=status.value,
            model_version=model.metadata.model_version,
        )
        return ProductSalePricePredictionRead(
            product_id=product_id,
            as_of=at,
            status=status,
            disclaimer=PREDICTION_DISCLAIMER,
            model_version=model.metadata.model_version,
            training_data_size=model.metadata.training_data_size,
            feature_version=model.metadata.feature_version,
            predictions=predictions,
            insufficient=insufficient,
        )


def load_training_corpus(session: Session) -> tuple[list, list]:
    """Load stored observations and sale events for offline training.

    Uses only rows already in the database. Does not invent prices or events.
    """
    from app.sales.models import SaleEventRecord, SalePricePoint

    events_repo = SaleEventRepository(session)
    products_repo = ProductRepository(session)
    snapshots_repo = PriceSnapshotRepository(session)
    events: list[SaleEventRecord] = [
        SaleEventService._record(row) for row in events_repo.list(limit=100_000)
    ]
    points: list[SalePricePoint] = []
    for product in products_repo.list(limit=100_000):
        for snapshot in snapshots_repo.history_for_product(product.id):
            listing = snapshot.retailer_product
            variant = listing.product_variant
            points.append(
                SaleEventService._point_from_snapshot(snapshot, product=product, variant=variant)
            )
    return points, events
