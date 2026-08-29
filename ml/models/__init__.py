"""Trained model artifacts live under `artifacts/` (gitignored)."""

from ml.models.artifact import (
    latest_version,
    make_model_version,
    read_metadata,
    save_artifact,
)

__all__ = ["latest_version", "make_model_version", "read_metadata", "save_artifact"]
