"""Train the Phase 10 sale-price model from stored observations and sale events.

Usage (from `backend/`, after `pip install -e ".[dev,ml]"`):

    python -m scripts.train_sale_price_model

If the database does not contain enough legitimate labeled history, the process logs
INSUFFICIENT_DATA and does not write a model. It never fabricates training rows.
"""

from __future__ import annotations

from app.db.session import SessionLocal
from app.observability.logging import get_logger
from app.services.sale_price_prediction_service import load_training_corpus
from ml.enums import PredictionStatus
from ml.training.train import train

logger = get_logger(__name__)


def main() -> int:
    session = SessionLocal()
    try:
        points, events = load_training_corpus(session)
        result = train(points, events)
        extra = {
            "status": result.status.value,
            "training_data_size": result.training_data_size,
            "observation_count": len(points),
            "event_count": len(events),
        }
        if result.status is PredictionStatus.INSUFFICIENT_DATA and result.insufficient is not None:
            extra["code"] = result.insufficient.code.value
            extra["reason"] = result.insufficient.reason
            logger.info("ml.training.cli.insufficient_data", extra=extra)
            return 2
        if result.metadata is not None:
            extra.update(
                {
                    "model_version": result.metadata.model_version,
                    "mae": result.metadata.mae,
                    "rmse": result.metadata.rmse,
                    "artifact_dir": result.artifact_dir,
                }
            )
        logger.info("ml.training.cli.completed", extra=extra)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
