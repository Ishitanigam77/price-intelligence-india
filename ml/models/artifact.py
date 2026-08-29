"""Model artifact versioning: booster, preprocessor, and metadata on disk."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ml.config import FEATURE_VERSION, MODEL_TYPE
from ml.preprocessing.encode import FeaturePreprocessor
from ml.types import ModelMetadata

LATEST_POINTER = "latest.json"
MODEL_FILE = "model.json"
PREPROCESSOR_FILE = "preprocessor.json"
METADATA_FILE = "metadata.json"


def make_model_version(*, trained_at: datetime | None = None) -> str:
    stamp = (trained_at or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"sale-price-xgb-{FEATURE_VERSION}-{stamp}"


def version_dir(root: Path, model_version: str) -> Path:
    return root / model_version


def save_artifact(
    *,
    root: Path,
    metadata: ModelMetadata,
    booster: object,
    preprocessor: FeaturePreprocessor,
) -> Path:
    directory = version_dir(root, metadata.model_version)
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / MODEL_FILE
    booster.save_model(str(model_path))  # type: ignore[attr-defined]
    (directory / PREPROCESSOR_FILE).write_text(
        json.dumps(preprocessor.to_state(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (directory / METADATA_FILE).write_text(
        metadata.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (root / LATEST_POINTER).write_text(
        json.dumps({"model_version": metadata.model_version, "model_type": MODEL_TYPE}, indent=2),
        encoding="utf-8",
    )
    return directory


def read_metadata(directory: Path) -> ModelMetadata:
    payload = json.loads((directory / METADATA_FILE).read_text(encoding="utf-8"))
    return ModelMetadata.model_validate(payload)


def read_preprocessor(directory: Path) -> FeaturePreprocessor:
    payload = json.loads((directory / PREPROCESSOR_FILE).read_text(encoding="utf-8"))
    return FeaturePreprocessor.from_state(payload)


def latest_version(root: Path) -> str | None:
    pointer = root / LATEST_POINTER
    if not pointer.is_file():
        return None
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    version = payload.get("model_version")
    return str(version) if version else None
